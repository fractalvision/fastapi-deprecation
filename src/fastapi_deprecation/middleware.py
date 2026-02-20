from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import Request, Response
from starlette.types import ASGIApp, Receive, Scope, Send, Message
from starlette.datastructures import MutableHeaders

from .dependencies import DeprecationDependency
from .engine import (
    evaluate_deprecation,
    ActionType,
    apply_headers,
    build_block_response,
    DeprecationConfig,
    execute_telemetry,
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
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

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
        result = evaluate_deprecation(matched_config, now)

        # original dependency for callback if provided
        original_dep = self.original_deprecations[matched_prefix]

        if result.action == ActionType.BLOCK:
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

            await send(message)

        await self.app(scope, receive, send_wrapper)

        # Reconstruct response for callback
        res = Response(status_code=status_code_captured)
        res.raw_headers = headers_captured
        await execute_telemetry(request, res, original_dep)
