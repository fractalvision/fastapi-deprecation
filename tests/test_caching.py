from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_deprecation import (
    deprecated,
    DeprecationDependency,
    DeprecationMiddleware,
)


def test_cache_control_decorator():
    app = FastAPI()

    # Set sunset 1 hour from now
    now = datetime.now(timezone.utc)
    sunset_dt = now + timedelta(hours=1)

    @app.get("/api/test")
    @deprecated(sunset_date=sunset_dt, inject_cache_control=True)
    def test_ep():
        return {"msg": "hello"}

    client = TestClient(app)
    res = client.get("/api/test")

    assert res.status_code == 200
    assert "Cache-Control" in res.headers
    # Expect max-age around 3600 +/- 1
    assert (
        "max-age=359" in res.headers["Cache-Control"]
        or "max-age=360" in res.headers["Cache-Control"]
    )


def test_cache_control_middleware():
    app = FastAPI()

    now = datetime.now(timezone.utc)
    sunset_dt = now + timedelta(minutes=5)

    app.add_middleware(
        DeprecationMiddleware,
        deprecations={
            "/api/v1": DeprecationDependency(
                sunset_date=sunset_dt, inject_cache_control=True
            )
        },
    )

    @app.get("/api/v1/test")
    def test_v1():
        return {"msg": "v1"}

    client = TestClient(app)
    res = client.get("/api/v1/test")

    assert res.status_code == 200
    assert "Cache-Control" in res.headers
    assert (
        "max-age=29" in res.headers["Cache-Control"]
        or "max-age=30" in res.headers["Cache-Control"]
    )


def test_cache_control_disabled_by_default():
    app = FastAPI()
    now = datetime.now(timezone.utc)
    sunset_dt = now + timedelta(hours=1)

    @app.get("/api/no-cache")
    @deprecated(sunset_date=sunset_dt)
    def test_no_cache():
        return {"msg": "hello"}

    client = TestClient(app)
    res = client.get("/api/no-cache")

    if "Cache-Control" in res.headers:
        assert "max-age" not in res.headers["Cache-Control"]
