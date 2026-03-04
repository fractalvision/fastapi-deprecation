from typing import Protocol, runtime_checkable, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from ..engine import DeprecationConfig


class DeprecationPhase(str, Enum):
    """Represents the active lifecycle phase of the endpoint during the request."""

    WARN = "warn"
    BLOCK = "block"


@runtime_checkable
class AbstractMetricsStore(Protocol):
    """
    Protocol defining the required interface for all Deprecation Metrics Storage backends.
    """

    async def increment(
        self,
        path: str,
        method: str,
        phase: DeprecationPhase,
        config: "DeprecationConfig",
    ) -> None:
        """
        Increment the request counter for a specific deprecated endpoint.

        Args:
            path: The grouped route path (e.g. '/v1/users/{user_id}')
            method: The HTTP method (e.g. 'GET', 'POST')
            phase: The deprecation phase of the request ('warn' or 'block')
            config: The active deprecation configuration for metadata extraction
        """
        ...

    async def export(self) -> dict | str:
        """
        Export the aggregated metrics.

        Returns:
            A JSON-serializable dictionary for standard implementations,
            or a formatted text string (e.g., for Prometheus exposition).
        """
        ...
