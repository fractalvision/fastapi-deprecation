import pytest
import pytest_asyncio
from fastapi import Response

from fastapi_deprecation.engine import DeprecationConfig
from fastapi_deprecation.metrics import DeprecationTracker
from fastapi_deprecation.metrics.redis import RedisMetricsStore


@pytest_asyncio.fixture
async def redis_tracker():
    try:
        import fakeredis.aioredis
    except ImportError:
        pytest.skip("fakeredis is not installed")

    client = fakeredis.aioredis.FakeRedis()
    store = RedisMetricsStore(client)
    tracker = DeprecationTracker(store)

    yield tracker
    await client.flushall()


@pytest.mark.asyncio
async def test_redis_metrics_aggregation(redis_tracker: DeprecationTracker):
    # Mock some raw requests and responses
    req_warn = {"method": "GET", "path": "/v1/auth", "type": "http"}
    res_warn = Response(status_code=200)

    req_block = {"method": "DELETE", "path": "/v1/admin", "type": "http"}
    res_block = Response(status_code=410)

    from datetime import datetime, timezone

    config = DeprecationConfig(sunset_date=datetime.now(timezone.utc))

    # Simulate hits
    await redis_tracker.record_usage(req_warn, res_warn, config)
    await redis_tracker.record_usage(req_warn, res_warn, config)
    await redis_tracker.record_usage(req_block, res_block, config)
    await redis_tracker.record_usage(req_block, res_block, config)
    await redis_tracker.record_usage(req_block, res_block, config)

    # Export directly from redis via the Tracker
    exported = await redis_tracker.export_json()
    metrics = exported["fastapi_deprecation_requests_total"]

    assert "GET /v1/auth" in metrics
    assert metrics["GET /v1/auth"]["warn"] == 2
    assert metrics["GET /v1/auth"]["block"] == 0
    assert metrics["GET /v1/auth"].get("sunset_date") is not None

    assert "DELETE /v1/admin" in metrics
    assert metrics["DELETE /v1/admin"]["warn"] == 0
    assert metrics["DELETE /v1/admin"]["block"] == 3
    assert metrics["DELETE /v1/admin"].get("sunset_date") is not None
