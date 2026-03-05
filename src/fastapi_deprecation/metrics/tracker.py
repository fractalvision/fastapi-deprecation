import inspect
from fastapi import Request, Response
from typing import Mapping

from ..engine import DeprecationConfig
from .base import AbstractMetricsStore, DeprecationPhase
from .memory import InMemoryMetricsStore


class DeprecationTracker:
    """
    Core Metrics Aggregator.

    Binds to the `set_deprecation_callback` pipeline to intercept and record
    live production traffic hitting deprecated or sunset endpoints.
    """

    def __init__(self, store: AbstractMetricsStore | None = None):
        """
        Initialize the tracker with a specific storage backend.
        If no store is provided, defaults to the single-worker InMemoryMetricsStore.
        """
        self.store = store or InMemoryMetricsStore()

    def _extract_path_and_method(self, request: Request | Mapping) -> tuple[str, str]:
        """
        Safely extract the route path and method from an ASGI request/mapping.
        WebSocket scopes use 'websocket' as the method.
        """
        if hasattr(request, "scope"):
            scope = request.scope
        elif isinstance(request, dict):
            scope = request
        else:
            return "unknown", "unknown"

        # Prioritize matched route definition if available to prevent
        # path parameter cardinality explosions (e.g., track /users/{id} not /users/1)
        path = "unknown"
        if "route" in scope and hasattr(scope["route"], "path"):
            path = scope["route"].path
        elif "path" in scope:
            path = scope["path"]

        method = (
            "websocket"
            if scope.get("type") == "websocket"
            else scope.get("method", "GET")
        )

        return path, method.upper()

    def _determine_phase(self, response: Response | None) -> DeprecationPhase:
        """
        Determine if the request was blocked by a sunset/brownout, or just received a warning.
        """
        # If response is None (e.g., active WebSocket stream), we default to WARN unless aborted
        if response is None:
            return DeprecationPhase.WARN

        status = getattr(response, "status_code", 200)
        # We consider HTTP 410 Gone as our native BLOCK indicator
        if status == 410:
            return DeprecationPhase.BLOCK

        return DeprecationPhase.WARN

    async def record_usage(
        self,
        request: Request | Mapping,
        response: Response | None,
        config: DeprecationConfig,
    ) -> None:
        """
        The global engine callback interceptor.
        Extracts metadata and increments the storage backend.
        """
        path, method = self._extract_path_and_method(request)
        phase = self._determine_phase(response)

        # Dispatch to the active storage plugin
        try:
            if inspect.iscoroutinefunction(self.store.increment):
                await self.store.increment(path, method, phase, config)
            else:
                self.store.increment(path, method, phase, config)  # type: ignore
        except Exception:
            # We must never crash the user's application because metrics failed
            # Logging could be added here in the future
            pass

    async def export_json(self) -> dict:
        """Export metrics formatted as a JSON dictionary."""
        res = self.store.export()
        if inspect.iscoroutine(res):
            res = await res
        if isinstance(res, str):
            raise NotImplementedError(
                f"The configured store <{self.store.__class__.__name__}> does not support JSON dictionary export. "
                "Instead, use `tracker.export_text()` method and return the result as a plain text string."
            )
        return dict(res)  # type: ignore

    async def export_text(self) -> str:
        """Export metrics formatted as raw text (e.g., for Prometheus exposition)."""
        res = self.store.export()
        if inspect.iscoroutine(res):
            res = await res
        if isinstance(res, dict):
            import json

            return json.dumps(res, indent=2)
        return str(res)
