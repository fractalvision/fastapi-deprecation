from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response, status
from starlette.responses import Response as StarletteResponse

from .engine import (
    ActionType,
    DeprecationConfig,
    apply_headers,
    build_block_response,
    execute_telemetry,
    process_deprecation,
)
from .utils import DateInput, parse_date


class DeprecationSunset(Exception):
    def __init__(self, response: StarletteResponse):
        self.response = response


async def sunset_exception_handler(request: Request, exc: DeprecationSunset):
    return exc.response


class DeprecationDependency:
    """
    A dependency that can be used to deprecate an endpoint or router.

    Args:
        deprecation_date (Optional[DateInput]): The date when the endpoint is deprecated.
        sunset_date (Optional[DateInput]): The date when the endpoint is sunset.
        alternative (Optional[str]): The alternative endpoint to redirect to.
        link (Optional[str]): The link to the deprecation information (policy or migration guide).
        links (Optional[dict[str, str]]): Additional links for deprecation information (newer versions, etc.).
        brownouts (Optional[list[tuple[DateInput, DateInput]]]): List of brownout periods.
        detail (Optional[str]): Additional detail about the deprecation.
        response (Optional[Callable[[], StarletteResponse] | StarletteResponse]): Custom response to return.
        inject_cache_control (bool): Whether to inject cache control headers.
        cache_tag (Optional[str]): Cache tag for the deprecation.
        brownout_probability (float): Probability of a brownout.
        progressive_brownout (bool): Whether to use progressive brownout.
    """

    def __init__(
        self,
        deprecation_date: Optional[DateInput] = None,
        sunset_date: Optional[DateInput] = None,
        alternative: Optional[str] = None,
        alternative_status: int = status.HTTP_301_MOVED_PERMANENTLY,
        link: Optional[str] = None,
        links: Optional[dict[str, str]] = None,
        brownouts: Optional[list[tuple[DateInput, DateInput]]] = None,
        detail: Optional[str] = None,
        response: Optional[Callable[[], StarletteResponse] | StarletteResponse] = None,
        inject_cache_control: bool = False,
        cache_tag: Optional[str] = None,
        brownout_probability: float = 0.0,
        progressive_brownout: bool = False,
    ):
        dep_date = parse_date(deprecation_date) if deprecation_date else None
        sun_date = parse_date(sunset_date) if sunset_date else None

        parsed_brownouts = []
        if brownouts:
            for start, end in brownouts:
                parsed_brownouts.append((parse_date(start), parse_date(end)))

        self.config = DeprecationConfig(
            deprecation_date=dep_date,
            sunset_date=sun_date,
            brownouts=parsed_brownouts,
            alternative=alternative,
            alternative_status=alternative_status,
            link=link,
            links=links,
            detail=detail,
            custom_response=response,
            inject_cache_control=inject_cache_control,
            cache_tag=cache_tag,
            brownout_probability=brownout_probability,
            progressive_brownout=progressive_brownout,
        )

    def __getattr__(self, item):
        """Pass through attribute accesses to the internal DeprecationConfig for backwards compatibility."""
        return getattr(self.config, item)

    async def __call__(self, request: Request, response: Response):
        now = datetime.now(timezone.utc)
        result = process_deprecation(self.config, now)

        if result.action == ActionType.BLOCK:
            dummy_res = build_block_response(self.config, result)
            await execute_telemetry(request, dummy_res, self)

            if self.config.custom_response:
                raise DeprecationSunset(dummy_res)

            if self.config.alternative:
                headers = dict(result.headers)
                headers["Location"] = self.config.alternative
                raise HTTPException(
                    status_code=self.config.alternative_status,
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
