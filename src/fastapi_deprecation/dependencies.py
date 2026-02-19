from datetime import datetime, timezone
from typing import Optional, Callable
import inspect

from fastapi import Request, Response, HTTPException, status
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


class DeprecationDependency:
    def __init__(
        self,
        deprecation_date: Optional[DateInput] = None,
        sunset_date: Optional[DateInput] = None,
        alternative: Optional[str] = None,
        link: Optional[str] = None,
        brownouts: Optional[list[tuple[DateInput, DateInput]]] = None,
        detail: Optional[str] = None,
    ):
        self.deprecation_date = (
            parse_date(deprecation_date) if deprecation_date else None
        )
        self.sunset_date = parse_date(sunset_date) if sunset_date else None
        self.alternative = alternative
        self.link = link
        self.brownouts = []
        if brownouts:
            for start, end in brownouts:
                self.brownouts.append((parse_date(start), parse_date(end)))
        self.detail = detail

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

            if self.link:
                existing_link = response.headers.get("Link", "")
                new_link = f'<{self.link}>; rel="deprecation"'
                if existing_link:
                    response.headers["Link"] = f"{existing_link}, {new_link}"
                else:
                    response.headers["Link"] = new_link

            if self.sunset_date:
                response.headers["Sunset"] = format_sunset_date(self.sunset_date)
