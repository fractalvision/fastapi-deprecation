from datetime import datetime, timezone
from typing import Optional, Callable
import inspect

from fastapi import Request, Response, HTTPException, status
from starlette.responses import Response as StarletteResponse
from .utils import format_deprecation_date, format_sunset_date, parse_date, DateInput

# Global callback for telemetry
_DEPRECATION_CALLBACK: Optional[
    Callable[[Request, Response, "DeprecationDependency"], None]
] = None


def set_deprecation_callback(
    callback: Callable[[Request, Response, "DeprecationDependency"], None]
):
    global _DEPRECATION_CALLBACK
    _DEPRECATION_CALLBACK = callback


class DeprecationSunset(Exception):
    def __init__(self, response: StarletteResponse):
        self.response = response


async def sunset_exception_handler(request: Request, exc: DeprecationSunset):
    return exc.response


class DeprecationDependency:
    def __init__(
        self,
        deprecation_date: Optional[DateInput] = None,
        sunset_date: Optional[DateInput] = None,
        alternative: Optional[str] = None,
        link: Optional[str] = None,
        links: Optional[dict[str, str]] = None,
        brownouts: Optional[list[tuple[DateInput, DateInput]]] = None,
        detail: Optional[str] = None,
        response: Optional[Callable[[], StarletteResponse] | StarletteResponse] = None,
        inject_cache_control: bool = False,
    ):
        self.deprecation_date = (
            parse_date(deprecation_date) if deprecation_date else None
        )
        self.sunset_date = parse_date(sunset_date) if sunset_date else None

        if (
            self.deprecation_date
            and self.sunset_date
            and self.deprecation_date > self.sunset_date
        ):
            raise ValueError("deprecation_date cannot be later than sunset_date")
        self.alternative = alternative
        self.links = dict(links) if links else {}
        if link:
            self.links["deprecation"] = link
        self.brownouts = []
        if brownouts:
            for start, end in brownouts:
                self.brownouts.append((parse_date(start), parse_date(end)))
        self.detail = detail
        self.custom_response = response
        self.inject_cache_control = inject_cache_control

    async def __call__(self, request: Request, response: Response):
        now = datetime.now(timezone.utc)

        # 1. Check Sunset (Blocking) or Brownout
        is_sunset = False
        if self.sunset_date and now >= self.sunset_date:
            is_sunset = True

        # Check brownouts if not already sunset
        if not is_sunset and self.brownouts:
            for start, end in self.brownouts:
                if start <= now <= end:
                    is_sunset = True
                    break

        if is_sunset:
            if self.custom_response:
                if isinstance(self.custom_response, StarletteResponse):
                    res = self.custom_response
                else:
                    res = self.custom_response()

                dt_to_emit = self.deprecation_date if self.deprecation_date else now
                res.headers["Deprecation"] = format_deprecation_date(dt_to_emit)

                if self.links:
                    existing_link = res.headers.get("Link", "")
                    new_links = [
                        f'<{url}>; rel="{rel}"' for rel, url in self.links.items()
                    ]
                    all_links_str = ", ".join(new_links)
                    if existing_link:
                        res.headers["Link"] = f"{existing_link}, {all_links_str}"
                    else:
                        res.headers["Link"] = all_links_str

                if self.sunset_date:
                    res.headers["Sunset"] = format_sunset_date(self.sunset_date)

                raise DeprecationSunset(res)

            if self.alternative:
                # 301 Moved Permanently
                # We raise HTTPException so it interrupts the flow.
                # Use headers={"Location": ...} for 301.
                raise HTTPException(
                    status_code=status.HTTP_301_MOVED_PERMANENTLY,
                    detail=self.detail or "Endpoint is deprecated and replaced.",
                    headers={"Location": self.alternative},
                )
            else:
                # 410 Gone
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail=self.detail
                    or "Endpoint is deprecated and no longer available.",
                )

        # 2. Check Deprecation (Warning Headers)
        # RFC 9745: "If the date is in the future, it indicates that the resource will be deprecated at that time."
        # So we ALWAYS emit the header if a date is configured.
        should_emit_header = False

        if self.deprecation_date:
            should_emit_header = True
        else:
            # If no date, it's deprecated "now" (active deprecation)
            should_emit_header = True

        if should_emit_header:
            dt_to_emit = self.deprecation_date if self.deprecation_date else now
            response.headers["Deprecation"] = format_deprecation_date(dt_to_emit)

            if _DEPRECATION_CALLBACK:
                try:
                    # Let's support sync callback for now.
                    if inspect.iscoroutinefunction(_DEPRECATION_CALLBACK):
                        await _DEPRECATION_CALLBACK(request, response, self)
                    else:
                        _DEPRECATION_CALLBACK(request, response, self)
                except Exception:
                    # Don't fail request if telemetry fails
                    pass

            if self.links:
                existing_link = response.headers.get("Link", "")
                new_links = [f'<{url}>; rel="{rel}"' for rel, url in self.links.items()]
                all_links_str = ", ".join(new_links)
                if existing_link:
                    response.headers["Link"] = f"{existing_link}, {all_links_str}"
                else:
                    response.headers["Link"] = all_links_str

            if self.sunset_date:
                response.headers["Sunset"] = format_sunset_date(self.sunset_date)

                if self.inject_cache_control:
                    delta = self.sunset_date - now
                    seconds = int(delta.total_seconds())
                    if seconds > 0:
                        existing_cc = response.headers.get("Cache-Control", "")
                        new_cc = f"max-age={seconds}"
                        if existing_cc:
                            response.headers[
                                "Cache-Control"
                            ] = f"{existing_cc}, {new_cc}"
                        else:
                            response.headers["Cache-Control"] = new_cc
