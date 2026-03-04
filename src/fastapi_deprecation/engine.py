import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import Request, Response, status
from starlette.responses import Response as StarletteResponse

from .utils import format_deprecation_date, format_sunset_date

# Global callbacks for telemetry
_DEPRECATION_CALLBACKS: Optional[List[Callable[[Request, Response, Any], None]]] = []


def set_deprecation_callback(callback: Callable[[Request, Response, Any], None]):
    """Set a global callback for telemetry."""
    global _DEPRECATION_CALLBACKS
    if callback:
        _DEPRECATION_CALLBACKS.append(callback)


def get_deprecation_callbacks() -> (
    Optional[List[Callable[[Request, Response, Any], None]]]
):
    return _DEPRECATION_CALLBACKS


async def execute_telemetry(
    request: Request, response: Response, dep_config_or_dependency: Any
):
    """Safely execute the registered telemetry callback if one exists."""
    callbacks = get_deprecation_callbacks()
    if callbacks:
        try:
            for callback in callbacks:
                if inspect.iscoroutinefunction(callback):
                    await callback(request, response, dep_config_or_dependency)
                else:
                    callback(request, response, dep_config_or_dependency)
        except Exception as e:
            logging.getLogger("fastapi_deprecation").error(
                f"Telemetry callback failed on call to <{callback.__name__}>: {e}"
            )


class ActionType(Enum):
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class DeprecationConfig:
    """
    Configuration for deprecation.

    Attributes:
        deprecation_date (Optional[datetime]): The date when the endpoint is deprecated.
        sunset_date (Optional[datetime]): The date when the endpoint is sunset.
        brownouts (List[Tuple[datetime, datetime]]): List of brownout periods.
        alternative (Optional[str]): The alternative endpoint to redirect to.
        link (Optional[str]): The link to the deprecation information (policy or migration guide).
        links (Optional[dict[str, str]]): Additional links for deprecation information (newer versions, etc.).
        detail (Optional[str]): Additional detail about the deprecation.
        response (Optional[Callable[[], StarletteResponse] | StarletteResponse]): Custom response to return.
        inject_cache_control (bool): Whether to inject cache control headers.
        cache_tag (Optional[str]): Cache tag for the deprecation.
        brownout_probability (float): Probability of a brownout.
        progressive_brownout (bool): Whether to use progressive brownout.
    """

    deprecation_date: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    brownouts: List[Tuple[datetime, datetime]] = field(default_factory=list)
    alternative: Optional[str] = None
    alternative_status: int = status.HTTP_301_MOVED_PERMANENTLY
    link: Optional[str] = None
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

        if self.brownout_probability > 0 and self.progressive_brownout:
            raise ValueError(
                "Cannot use both static brownout_probability and progressive_brownout"
            )

        if self.progressive_brownout and not (
            self.deprecation_date and self.sunset_date
        ):
            raise ValueError(
                "progressive_brownout requires both deprecation_date and sunset_date"
            )

        if not (0.0 <= self.brownout_probability <= 1.0):
            raise ValueError("brownout_probability must be between 0.0 and 1.0")


@dataclass
class DeprecationResult:
    action: ActionType
    headers: Dict[str, str]


def process_deprecation(
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
    if not is_sunset:
        if config.progressive_brownout:
            # Progressive: failure probability scales from 0.0 at deprecation_date to 1.0 at sunset_date
            # (Validation ensures deprecation_date and sunset_date are present)
            if now >= config.deprecation_date:
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

    dt_to_emit = config.deprecation_date if config.deprecation_date else now
    headers["Deprecation"] = format_deprecation_date(dt_to_emit)

    links = config.links and config.links.copy() or {}

    if config.link:
        if is_sunset:
            links["sunset"] = config.link
        else:
            links["deprecation"] = config.link

    if links:
        response_links = [f'<{url}>; rel="{rel}"' for rel, url in links.items()]
        headers["Link"] = ", ".join(response_links)

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
    """Constructs an overriding Starlette Response for blocking actions with the specified status code."""
    from starlette.responses import JSONResponse, PlainTextResponse

    if config.custom_response:
        if isinstance(config.custom_response, StarletteResponse):
            response = config.custom_response
        else:
            response = config.custom_response()
    elif config.alternative:
        response = PlainTextResponse(
            content=config.detail or "Endpoint is deprecated and replaced.",
            status_code=config.alternative_status,
        )
        response.headers["Location"] = config.alternative
    else:
        response = JSONResponse(
            content={
                "detail": config.detail
                or "Endpoint is deprecated and no longer available."
            },
            status_code=status.HTTP_410_GONE,
        )

    apply_headers(response.headers, result.headers)
    return response


async def send_websocket_block_response(
    config: DeprecationConfig, result: DeprecationResult, send: Callable
) -> None:
    """Sends a raw ASGI HTTP response directly rejecting the WebSocket upgrade."""
    content = config.detail or "Endpoint is deprecated and no longer available."
    status_code = status.HTTP_410_GONE

    if config.alternative:
        content = config.detail or "Endpoint is deprecated and replaced."
        status_code = config.alternative_status

    headers = [
        (b"content-type", b"text/plain; charset=utf-8"),
        (b"content-length", str(len(content)).encode("utf-8")),
    ]

    if config.alternative:
        headers.append((b"location", config.alternative.encode("utf-8")))

    for k, v in result.headers.items():
        headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))

    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": content.encode("utf-8"),
        }
    )
