from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from fastapi_deprecation import (
    deprecated,
    DeprecationDependency,
    auto_deprecate_openapi,
)


def test_decorator_custom_response():
    app = FastAPI()

    custom_res = JSONResponse(
        content={"message": "This endpoint is permanently gone. Please visit /v2."},
        status_code=410,
    )

    @app.get("/api/v1/test")
    @deprecated(sunset_date="2020-01-01", response=custom_res)
    def test_v1():
        return {"msg": "v1"}

    client = TestClient(app)

    res = client.get("/api/v1/test")
    assert res.status_code == 410
    assert res.json() == {
        "message": "This endpoint is permanently gone. Please visit /v2."
    }
    assert "Sunset" in res.headers
    assert "Deprecation" in res.headers


def test_decorator_custom_response_callable():
    app = FastAPI()

    def make_res():
        return JSONResponse(content={"message": "Factory response"}, status_code=410)

    @app.get("/api/v1/factory")
    @deprecated(sunset_date="2020-01-01", response=make_res)
    def test_factory():
        return {"msg": "v1"}

    client = TestClient(app)

    res = client.get("/api/v1/factory")
    assert res.status_code == 410
    assert res.json() == {"message": "Factory response"}
    assert "Sunset" in res.headers


def test_dependency_custom_response():
    app = FastAPI()

    # Register exception handler
    auto_deprecate_openapi(app)

    custom_res = JSONResponse(
        content={"message": "Custom Error via Dependency"}, status_code=410
    )

    @app.get(
        "/api/v2/test",
        dependencies=[
            Depends(
                DeprecationDependency(sunset_date="2020-01-01", response=custom_res)
            )
        ],
    )
    def test_v2():
        return {"msg": "v2"}

    client = TestClient(app)

    res = client.get("/api/v2/test")
    assert res.status_code == 410
    assert res.json() == {"message": "Custom Error via Dependency"}
    assert "Sunset" in res.headers
