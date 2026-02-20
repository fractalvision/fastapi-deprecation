from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable, Any
import logging
import inspect

from starlette.responses import Response as StarletteResponse
from fastapi import Request, Response

from .utils import format_deprecation_date, format_sunset_date

# Global callback for telemetry
_DEPRECATION_CALLBACK: Optional[Callable[[Request, Response, Any], None]] = None


def set_deprecation_callback(callback: Callable[[Request, Response, Any], None]):
    global _DEPRECATION_CALLBACK
    _DEPRECATION_CALLBACK = callback


def get_deprecation_callback() -> Optional[Callable[[Request, Response, Any], None]]:
    return _DEPRECATION_CALLBACK


async def execute_telemetry(
    request: Request, response: Response, dep_config_or_dependency: Any
):
    """Safely execute the registered telemetry callback if one exists."""
    callback = get_deprecation_callback()
    if callback:
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(request, response, dep_config_or_dependency)
            else:
                callback(request, response, dep_config_or_dependency)
        except Exception as e:
            logging.getLogger("fastapi_deprecation").error(
                f"Telemetry callback failed: {e}"
            )


class ActionType(Enum):
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class DeprecationConfig:
    deprecation_date: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    brownouts: List[Tuple[datetime, datetime]] = field(default_factory=list)
    alternative: Optional[str] = None
    links: Dict[str, str] = field(default_factory=dict)
    detail: Optional[str] = None
    custom_response: Optional[
        Callable[[], StarletteResponse] | StarletteResponse
    ] = None
    inject_cache_control: bool = False
    cache_tag: Optional[str] = None
    brownout_probability: float = 0.0
    progressive_brownout: bool = False

    def __post_init__(self):
        if (
            self.deprecation_date
            and self.sunset_date
            and self.deprecation_date > self.sunset_date
        ):
            raise ValueError("deprecation_date cannot be later than sunset_date")


@dataclass
class DeprecationResult:
    action: ActionType
    headers: Dict[str, str]


def evaluate_deprecation(
    config: DeprecationConfig, request_time: Optional[datetime] = None
) -> DeprecationResult:
    import random

    now = request_time or datetime.now(timezone.utc)
    headers: Dict[str, str] = {}

    is_sunset = False
    if config.sunset_date and now >= config.sunset_date:
        is_sunset = True

    if not is_sunset and config.brownouts:
        for start, end in config.brownouts:
            if start <= now <= end:
                is_sunset = True
                break

    # Chaos Engineering: Probabilistic Brownouts
    if not is_sunset and config.deprecation_date:
        if now >= config.deprecation_date:
            if config.progressive_brownout and config.sunset_date:
                # Progressive: failure probability scales from 0.0 at deprecation_date to 1.0 at sunset_date
                total_duration = (
                    config.sunset_date - config.deprecation_date
                ).total_seconds()
                elapsed_duration = (now - config.deprecation_date).total_seconds()

                if total_duration > 0:
                    probability = elapsed_duration / total_duration
                    if random.random() < probability:
                        is_sunset = True
            elif config.brownout_probability > 0:
                # Static: uniform failure chance during the whole deprecation window
                if random.random() < config.brownout_probability:
                    is_sunset = True

    should_emit_header = True if not config.deprecation_date else True

    if should_emit_header:
        dt_to_emit = config.deprecation_date if config.deprecation_date else now
        headers["Deprecation"] = format_deprecation_date(dt_to_emit)

        if config.links:
            new_links = [f'<{url}>; rel="{rel}"' for rel, url in config.links.items()]
            headers["Link"] = ", ".join(new_links)

        if config.sunset_date:
            headers["Sunset"] = format_sunset_date(config.sunset_date)

            if config.inject_cache_control and not is_sunset:
                delta = config.sunset_date - now
                seconds = int(delta.total_seconds())
                if seconds > 0:
                    headers["Cache-Control"] = f"max-age={seconds}"

        if config.cache_tag:
            headers["Cache-Tag"] = config.cache_tag
            headers["Surrogate-Key"] = config.cache_tag

    if is_sunset:
        return DeprecationResult(action=ActionType.BLOCK, headers=headers)
    else:
        return DeprecationResult(action=ActionType.WARN, headers=headers)


def apply_headers(target, headers: Dict[str, str]) -> None:
    """Safely apply DeprecationResult headers to a MutableHeaders or dict-like object."""
    for k, v in headers.items():
        if k in ("Link", "Cache-Control"):
            # Use get() for MutableHeaders, or direct access for dicts if safe
            existing = (
                target.get(k)
                if hasattr(target, "get")
                else (target[k] if k in target else None)
            )
            if existing:
                target[k] = f"{existing}, {v}"
            else:
                target[k] = v
        else:
            target[k] = v


def build_block_response(
    config: DeprecationConfig, result: DeprecationResult
) -> StarletteResponse:
    """Constructs an overriding Starlette Response for 410 or 301 blocking actions."""
    from starlette.responses import JSONResponse, PlainTextResponse

    if config.custom_response:
        if isinstance(config.custom_response, StarletteResponse):
            response = config.custom_response
        else:
            response = config.custom_response()
    elif config.alternative:
        response = PlainTextResponse(
            content=config.detail or "Endpoint is deprecated and replaced.",
            status_code=301,
        )
        response.headers["Location"] = config.alternative
    else:
        response = JSONResponse(
            content={
                "detail": config.detail
                or "Endpoint is deprecated and no longer available."
            },
            status_code=410,
        )

    apply_headers(response.headers, result.headers)
    return response
