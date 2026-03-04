from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import Request, Response
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .dependencies import DeprecationDependency
from .engine import (
    ActionType,
    DeprecationConfig,
    apply_headers,
    build_block_response,
    execute_telemetry,
    process_deprecation,
    send_websocket_block_response,
)


class DeprecationMiddleware:
    """
    Middleware to handle deprecation headers and blocking for entire path prefixes.
    Intercepts 404s and 200s to inject RFC 9745 context.
    """

    def __init__(
        self,
        app: ASGIApp,
        deprecations: Dict[str, DeprecationConfig | DeprecationDependency],
    ):
        self.app = app
        self.original_deprecations = deprecations

        normalized_deps = {}
        for prefix, dep in deprecations.items():
            if hasattr(dep, "config"):
                normalized_deps[prefix] = dep.config
            else:
                normalized_deps[prefix] = dep

        # Sort prefixes by length descending to match most specific first
        self.deprecations = dict(
            sorted(normalized_deps.items(), key=lambda item: len(item[0]), reverse=True)
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Request object constructor requires HTTP scope. For URL path extraction, we can
        # either use a dummy HTTP scope or just extract path manually.
        if scope["type"] == "websocket":
            # For websockets, we can still parse the URL path safely from scope
            path = scope.get("path", "")
            # Create a dummy HTTP scope to allow Request() to parsing,
            # purely so `execute_telemetry` doesn't break if it expects a Request object.
            # However, execute_telemetry isn't strictly necessary to send WebSockets
            # so we'll just parse the path here.
            from starlette.websockets import WebSocket

            request = WebSocket(scope, receive, send)
        else:
            request = Request(scope, receive)
            path = request.url.path

        # Find matching deprecation
        matched_config: Optional[DeprecationConfig] = None
        matched_prefix: Optional[str] = None
        for prefix, config in self.deprecations.items():
            if path.startswith(prefix):
                matched_config = config
                matched_prefix = prefix
                break

        if not matched_config:
            await self.app(scope, receive, send)
            return

        now = datetime.now(timezone.utc)
        result = process_deprecation(matched_config, now)

        # original dependency for callback if provided
        original_dep = self.original_deprecations[matched_prefix]

        if result.action == ActionType.BLOCK:
            if scope["type"] == "websocket":
                # For websockets, we must send raw ASGI HTTP response to deny upgrade
                await send_websocket_block_response(matched_config, result, send)
                # Reconstruct dummy response for telemetry
                dummy_res = Response(status_code=410)
                await execute_telemetry(request, dummy_res, original_dep)
                return
            else:
                response = build_block_response(matched_config, result)

                # Execute callback if configured
                await execute_telemetry(request, response, original_dep)

                await response(scope, receive, send)
                return

        # 2. Warning Phase
        status_code_captured = 200
        headers_captured = []

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code_captured, headers_captured
            if message["type"] == "http.response.start":
                status_code_captured = message["status"]
                headers = MutableHeaders(scope=message)

                apply_headers(headers, result.headers)
                headers_captured = headers.raw
            elif message["type"] == "websocket.accept":
                # Inject headers into websocket accept response
                ws_headers = message.get("headers", [])

                # Convert dict to mutable headers for easier modification
                # We need to create a dummy dict-like object to use apply_headers
                header_dict = {}
                for k, v in ws_headers:
                    header_dict[k.decode("utf-8")] = v.decode("utf-8")

                apply_headers(header_dict, result.headers)

                # Rebuild ASGI headers list
                new_ws_headers = []
                for k, v in header_dict.items():
                    new_ws_headers.append(
                        (k.lower().encode("utf-8"), v.encode("utf-8"))
                    )

                message["headers"] = new_ws_headers

            await send(message)

        await self.app(scope, receive, send_wrapper)

        # Reconstruct response for callback
        res = Response(status_code=status_code_captured)
        res.raw_headers = headers_captured
        await execute_telemetry(request, res, original_dep)
