from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_deprecation import (
    DeprecationDependency,
    DeprecationMiddleware,
    set_deprecation_callback,
)


def test_middleware_injection():
    app = FastAPI()

    app.add_middleware(
        DeprecationMiddleware,
        deprecations={
            "/api/v1": DeprecationDependency(deprecation_date="2024-01-01"),
            "/api/v2": DeprecationDependency(sunset_date="2020-01-01"),
        },
    )

    @app.get("/api/v1/test")
    def test_v1():
        return {"msg": "v1"}

    @app.get("/api/v2/test")
    def test_v2():
        return {"msg": "v2"}

    # Should be fine
    @app.get("/api/v3/test")
    def test_v3():
        return {"msg": "v3"}

    client = TestClient(app)

    # v1 is warning
    res1 = client.get("/api/v1/test")
    assert res1.status_code == 200
    assert "Deprecation" in res1.headers

    # v2 is sunset natively (middleware intercepted)
    res2 = client.get("/api/v2/test")
    assert res2.status_code == 410

    # what if v2 doesn't exist?
    res_not_found = client.get("/api/v2/missing")
    assert res_not_found.status_code == 410  # Intercepted before 404

    # v3 is unaffected
    res3 = client.get("/api/v3/test")
    assert res3.status_code == 200
    assert "Deprecation" not in res3.headers


def test_middleware_telemetry():
    calls = []

    def my_callback(req, res, dep):
        calls.append((req.url.path, res.status_code))

    set_deprecation_callback(my_callback)

    app = FastAPI()
    app.add_middleware(
        DeprecationMiddleware,
        deprecations={
            "/old": DeprecationDependency(deprecation_date="2024-01-01"),
            "/dead": DeprecationDependency(sunset_date="2020-01-01"),
        },
    )

    @app.get("/old/test")
    def old():
        return "old"

    client = TestClient(app)

    # Trigger warning
    client.get("/old/test")
    assert len(calls) == 1
    assert calls[0][0] == "/old/test"
    assert calls[0][1] == 200

    # Trigger sunset
    client.get("/dead/path")
    assert len(calls) == 2
    assert calls[1][0] == "/dead/path"
    assert calls[1][1] == 410

    # Reset callback for other tests
    set_deprecation_callback(None)
