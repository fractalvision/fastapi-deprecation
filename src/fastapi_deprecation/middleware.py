from datetime import datetime, timezone
from typing import Dict, Optional
import inspect

from fastapi import Request, Response
from starlette.types import ASGIApp, Receive, Scope, Send, Message
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.datastructures import MutableHeaders

from . import dependencies
from .dependencies import DeprecationDependency
from .utils import format_deprecation_date, format_sunset_date


class DeprecationMiddleware:
    """
    Middleware to handle deprecation headers and blocking for entire path prefixes.
    Intercepts 404s and 200s to inject RFC 9745 context.
    """

    def __init__(
        self,
        app: ASGIApp,
        deprecations: Dict[str, DeprecationDependency],
    ):
        self.app = app
        # Sort prefixes by length descending to match most specific first
        self.deprecations = dict(
            sorted(deprecations.items(), key=lambda item: len(item[0]), reverse=True)
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        # Find matching deprecation
        matched_dep: Optional[DeprecationDependency] = None
        for prefix, dep in self.deprecations.items():
            if path.startswith(prefix):
                matched_dep = dep
                break

        if not matched_dep:
            await self.app(scope, receive, send)
            return

        now = datetime.now(timezone.utc)

        # 1. Check Sunset / Brownout
        is_sunset = False
        if matched_dep.sunset_date and now >= matched_dep.sunset_date:
            is_sunset = True

        if not is_sunset and matched_dep.brownouts:
            for start, end in matched_dep.brownouts:
                if start <= now <= end:
                    is_sunset = True
                    break

        if is_sunset:
            # Block the request natively
            if matched_dep.alternative:
                response = PlainTextResponse(
                    content=matched_dep.detail
                    or "Endpoint is deprecated and replaced.",
                    status_code=301,
                    headers={"Location": matched_dep.alternative},
                )
            else:
                response = JSONResponse(
                    content={
                        "detail": matched_dep.detail
                        or "Endpoint is deprecated and no longer available."
                    },
                    status_code=410,
                )

            # Execute callback if configured
            if dependencies._DEPRECATION_CALLBACK:
                try:
                    if inspect.iscoroutinefunction(dependencies._DEPRECATION_CALLBACK):
                        await dependencies._DEPRECATION_CALLBACK(
                            request, response, matched_dep
                        )
                    else:
                        dependencies._DEPRECATION_CALLBACK(
                            request, response, matched_dep
                        )
                except Exception:
                    pass

            await response(scope, receive, send)
            return

        # 2. Warning Phase
        should_emit_header = True if not matched_dep.deprecation_date else True

        status_code_captured = 200
        headers_captured = []

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code_captured, headers_captured
            if message["type"] == "http.response.start":
                status_code_captured = message["status"]
                headers = MutableHeaders(scope=message)

                if should_emit_header:
                    dt_to_emit = (
                        matched_dep.deprecation_date
                        if matched_dep.deprecation_date
                        else now
                    )
                    headers["Deprecation"] = format_deprecation_date(dt_to_emit)

                    if matched_dep.links:
                        existing_link = headers.get("Link", "")
                        new_links = [
                            f'<{url}>; rel="{rel}"'
                            for rel, url in matched_dep.links.items()
                        ]
                        all_links_str = ", ".join(new_links)
                        if existing_link:
                            headers["Link"] = f"{existing_link}, {all_links_str}"
                        else:
                            headers["Link"] = all_links_str

                    if matched_dep.sunset_date:
                        headers["Sunset"] = format_sunset_date(matched_dep.sunset_date)

                        if matched_dep.inject_cache_control:
                            delta = matched_dep.sunset_date - now
                            seconds = int(delta.total_seconds())
                            if seconds > 0:
                                existing_cc = headers.get("Cache-Control", "")
                                new_cc = f"max-age={seconds}"
                                if existing_cc:
                                    headers[
                                        "Cache-Control"
                                    ] = f"{existing_cc}, {new_cc}"
                                else:
                                    headers["Cache-Control"] = new_cc

                headers_captured = headers.raw

            await send(message)

        await self.app(scope, receive, send_wrapper)

        if should_emit_header and dependencies._DEPRECATION_CALLBACK:
            # Reconstruct response for callback
            res = Response(status_code=status_code_captured)
            res.raw_headers = headers_captured
            try:
                if inspect.iscoroutinefunction(dependencies._DEPRECATION_CALLBACK):
                    await dependencies._DEPRECATION_CALLBACK(request, res, matched_dep)
                else:
                    dependencies._DEPRECATION_CALLBACK(request, res, matched_dep)
            except Exception:
                pass
