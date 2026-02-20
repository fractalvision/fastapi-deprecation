from datetime import datetime, timezone
from typing import Optional, Callable

from fastapi import Request, Response, HTTPException, status
from starlette.responses import Response as StarletteResponse
from .utils import parse_date, DateInput
from .engine import (
    DeprecationConfig,
    evaluate_deprecation,
    ActionType,
    apply_headers,
    build_block_response,
    execute_telemetry,
)


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
        dep_date = parse_date(deprecation_date) if deprecation_date else None
        sun_date = parse_date(sunset_date) if sunset_date else None

        parsed_brownouts = []
        if brownouts:
            for start, end in brownouts:
                parsed_brownouts.append((parse_date(start), parse_date(end)))

        parsed_links = dict(links) if links else {}
        if link:
            parsed_links["deprecation"] = link

        self.config = DeprecationConfig(
            deprecation_date=dep_date,
            sunset_date=sun_date,
            brownouts=parsed_brownouts,
            alternative=alternative,
            links=parsed_links,
            detail=detail,
            custom_response=response,
            inject_cache_control=inject_cache_control,
        )

    def __getattr__(self, item):
        """Pass through attribute accesses to the internal DeprecationConfig for backwards compatibility."""
        return getattr(self.config, item)

    async def __call__(self, request: Request, response: Response):
        now = datetime.now(timezone.utc)
        result = evaluate_deprecation(self.config, now)

        if result.action == ActionType.BLOCK:
            dummy_res = build_block_response(self.config, result)
            await execute_telemetry(request, dummy_res, self)

            if self.config.custom_response:
                raise DeprecationSunset(dummy_res)

            if self.config.alternative:
                headers = dict(result.headers)
                headers["Location"] = self.config.alternative
                raise HTTPException(
                    status_code=status.HTTP_301_MOVED_PERMANENTLY,
                    detail=self.config.detail or "Endpoint is deprecated and replaced.",
                    headers=headers,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail=self.config.detail
                    or "Endpoint is deprecated and no longer available.",
                    headers=result.headers,
                )

        # WARN Phase
        apply_headers(response.headers, result.headers)

        await execute_telemetry(request, response, self)
