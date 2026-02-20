from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_deprecation import DeprecationMiddleware, DeprecationDependency, deprecated


def test_multiple_link_relations():
    app = FastAPI()

    app.add_middleware(
        DeprecationMiddleware,
        deprecations={
            "/api/v1": DeprecationDependency(
                deprecation_date="2024-01-01",
                links={
                    "deprecation": "https://example.com/deprecation",
                    "successor-version": "https://example.com/v2",
                },
            )
        },
    )

    @app.get("/api/v1/test")
    def test_v1():
        return {"msg": "v1"}

    @app.get("/api/v2/test")
    @deprecated(
        deprecation_date="2024-01-01",
        link="https://example.com/single",
        links={"alternate": "https://example.com/alt"},
    )
    def test_v2():
        return {"msg": "v2"}

    client = TestClient(app)

    res1 = client.get("/api/v1/test")
    assert res1.status_code == 200
    assert "Link" in res1.headers
    assert 'rel="deprecation"' in res1.headers["Link"]
    assert 'rel="successor-version"' in res1.headers["Link"]

    res2 = client.get("/api/v2/test")
    assert res2.status_code == 200
    assert "Link" in res2.headers
    assert 'rel="deprecation"' in res2.headers["Link"]
    assert 'rel="alternate"' in res2.headers["Link"]
