from typing import TYPE_CHECKING
from .base import AbstractMetricsStore, DeprecationPhase

if TYPE_CHECKING:
    from ..engine import DeprecationConfig

try:
    from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST  # noqa: F401
except ImportError:
    # We delay raising the error until initialization
    pass


class PrometheusMetricsStore(AbstractMetricsStore):
    """
    A metrics store backed by the official prometheus_client library.
    Exports standard Prometheus exposition text for scraping.
    """

    def __init__(self):
        try:
            from prometheus_client import Counter, Info
        except ImportError:
            raise ImportError(
                "The PrometheusMetricsStore requires the 'prometheus-client' package. "
                "Install it using: pip install fastapi-deprecation[prometheus]"
            )

        # Register a global counter if it doesn't already exist
        self._counter = Counter(
            "fastapi_deprecation_requests_total",
            "Total requests hitting deprecated or sunset endpoints",
            ["path", "method", "phase"],
        )
        self._info = Info(
            "fastapi_deprecation_endpoint",
            "Metadata about deprecated endpoints",
            ["path", "method"],
        )

    async def increment(
        self,
        path: str,
        method: str,
        phase: DeprecationPhase,
        config: "DeprecationConfig",
    ) -> None:
        """Increment the Prometheus dimensional Counter and record Info metadata."""
        self._counter.labels(path=path, method=method, phase=phase.value).inc(1)

        labels = {}
        if config.deprecation_date:
            labels["deprecation_date"] = config.deprecation_date.isoformat()
        if config.sunset_date:
            labels["sunset_date"] = config.sunset_date.isoformat()

        if labels:
            self._info.labels(path=path, method=method).info(labels)

    async def export(self) -> str:
        """
        Export the metrics in Prometheus text exposition format.
        Useful for building a direct `/metrics/deprecation` endpoint for the scraper.
        """
        data = generate_latest()
        if isinstance(data, bytes):
            return data.decode("utf-8")
        return str(data)
