import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

from fastapi_deprecation import DeprecationMiddleware, set_deprecation_callback
from fastapi_deprecation.engine import DeprecationConfig
from fastapi_deprecation.metrics import DeprecationTracker, InMemoryMetricsStore


@pytest.fixture
def memory_tracker():
    tracker = DeprecationTracker(InMemoryMetricsStore())
    set_deprecation_callback(tracker.record_usage)
    return tracker


@pytest.fixture
def app(memory_tracker):
    app = FastAPI()
    app.add_middleware(
        DeprecationMiddleware,
        deprecations={
            "/v1/users": DeprecationConfig(
                deprecation_date=datetime.now(timezone.utc) - timedelta(days=1),
                sunset_date=datetime.now(timezone.utc) + timedelta(days=1),
            ),
            "/v1/payments": DeprecationConfig(
                sunset_date=datetime.now(timezone.utc) - timedelta(days=1)
            ),
        },
    )

    @app.get("/v1/users")
    async def get_users():
        return {"status": "ok"}

    @app.get("/v1/payments")
    async def get_payments():
        return {"status": "ok"}

    @app.get("/metrics")
    async def get_metrics():
        return await memory_tracker.export_json()

    return app


@pytest.mark.asyncio
async def test_in_memory_metrics_aggregation(app, memory_tracker):
    client = TestClient(app)

    # Hit the warning endpoint 3 times
    client.get("/v1/users")
    client.get("/v1/users")
    client.get("/v1/users")

    # Hit the blocked endpoint 2 times
    client.get("/v1/payments")
    client.get("/v1/payments")

    # Fetch metrics
    response = client.get("/metrics")
    assert response.status_code == 200
    metrics = response.json()["fastapi_deprecation_requests_total"]

    # Verify aggregation
    assert "GET /v1/users" in metrics
    assert metrics["GET /v1/users"]["warn"] == 3
    assert metrics["GET /v1/users"]["block"] == 0
    assert metrics["GET /v1/users"].get("deprecation_date") is not None
    assert metrics["GET /v1/users"].get("sunset_date") is not None

    assert "GET /v1/payments" in metrics
    assert metrics["GET /v1/payments"]["warn"] == 0
    assert metrics["GET /v1/payments"]["block"] == 2
    assert metrics["GET /v1/payments"].get("deprecation_date") is None
    assert metrics["GET /v1/payments"].get("sunset_date") is not None
