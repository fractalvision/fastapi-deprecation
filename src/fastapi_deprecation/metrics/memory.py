from typing import Dict, Any, TYPE_CHECKING
import asyncio
from .base import AbstractMetricsStore, DeprecationPhase

if TYPE_CHECKING:
    from ..engine import DeprecationConfig


class InMemoryMetricsStore(AbstractMetricsStore):
    """
    A simple dictionary-backed metrics store.

    WARNING: This store aggregates metrics in the memory of the current Python process.
    If you are running your application with multiple workers (e.g., `uvicorn --workers 4`),
    each worker will maintain completely isolated, separate metrics.

    For multi-worker production deployments, please install the `[redis]` or `[prometheus]`
    extensions and use a distributed storage backend.
    """

    def __init__(self):
        # Format: { "GET /v1/users": {"warn": 10, "block": 0} }
        self._counts: Dict[str, Dict[str, int]] = {}
        self._lock = asyncio.Lock()

    async def increment(
        self,
        path: str,
        method: str,
        phase: DeprecationPhase,
        config: "DeprecationConfig",
    ) -> None:
        key = f"{method} {path}"
        phase_key = phase.value

        async with self._lock:
            if key not in self._counts:
                self._counts[key] = {
                    "warn": 0,
                    "block": 0,
                    "deprecation_date": None,
                    "sunset_date": None,
                }
            self._counts[key][phase_key] += 1

            # Conditionally set the metadata if it hasn't been set yet
            if (
                self._counts[key]["deprecation_date"] is None
                and config.deprecation_date
            ):
                self._counts[key][
                    "deprecation_date"
                ] = config.deprecation_date.isoformat()
            if self._counts[key]["sunset_date"] is None and config.sunset_date:
                self._counts[key]["sunset_date"] = config.sunset_date.isoformat()

    async def export(self) -> dict[str, Any]:
        """Export the metrics as a standardized JSON dictionary."""
        async with self._lock:
            # Return a deep copy to prevent external mutation
            return {
                "fastapi_deprecation_requests_total": {
                    k: dict(v) for k, v in self._counts.items()
                }
            }
