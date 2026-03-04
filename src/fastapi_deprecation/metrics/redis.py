from typing import TYPE_CHECKING
from .base import AbstractMetricsStore, DeprecationPhase

if TYPE_CHECKING:
    from ..engine import DeprecationConfig

try:
    from redis.asyncio import Redis
except ImportError:

    class Redis:  # type: ignore
        pass


class RedisMetricsStore(AbstractMetricsStore):
    """
    A globally synchronized metrics store backed by Redis.
    Perfect for multi-worker environments (Gunicorn/Uvicorn) that need safe counter aggregation.
    """

    def __init__(self, client: "Redis", prefix: str = "fastapi_deprecation"):
        """
        Initialize with an active `redis.asyncio.Redis` client.

        Raises ImportError if the `[redis]` optional dependency is not installed.
        """
        try:
            import redis  # noqa: F401
        except ImportError:
            raise ImportError(
                "The RedisMetricsStore requires the 'redis' package. "
                "Install it using: pip install fastapi-deprecation[redis]"
            )

        self.client = client
        self.prefix = prefix

    async def increment(
        self,
        path: str,
        method: str,
        phase: DeprecationPhase,
        config: "DeprecationConfig",
    ) -> None:
        key = f"{self.prefix}:{method}:{path}"
        await self.client.hincrby(key, phase.value, 1)

        if config.deprecation_date:
            await self.client.hsetnx(
                key, "deprecation_date", config.deprecation_date.isoformat()
            )
        if config.sunset_date:
            await self.client.hsetnx(key, "sunset_date", config.sunset_date.isoformat())

    async def export(self) -> dict:
        """
        Export all keys matching the configured prefix into a JSON-serializable dictionary.
        """
        keys = await self.client.keys(f"{self.prefix}:*:*")
        result = {}
        for key in keys:
            if isinstance(key, bytes):
                key_str = key.decode("utf-8")
            else:
                key_str = key

            parts = key_str.split(":", 2)
            if len(parts) == 3:
                # Format: "GET /v1/users"
                path_method = f"{parts[1]} {parts[2]}"

                # Get the hash fields (warn, block)
                fields = await self.client.hgetall(key)

                # Decode bytes if necessary
                decoded_fields = {}
                for k, v in fields.items():
                    dk = k.decode("utf-8") if isinstance(k, bytes) else k
                    if dk in ("warn", "block"):
                        dv = int(v) if v else 0
                    else:
                        dv = v.decode("utf-8") if isinstance(v, bytes) else v
                    decoded_fields[dk] = dv

                # Ensure both phase fields are populated with at least 0, and append dates if found
                result[path_method] = {
                    "warn": decoded_fields.get("warn", 0),
                    "block": decoded_fields.get("block", 0),
                    "deprecation_date": decoded_fields.get("deprecation_date"),
                    "sunset_date": decoded_fields.get("sunset_date"),
                }

        return {"fastapi_deprecation_requests_total": result}
