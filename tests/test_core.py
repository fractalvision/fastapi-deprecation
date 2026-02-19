from fastapi import FastAPI, Request, Response, Depends
from fastapi.testclient import TestClient
from fastapi_deprecation import deprecated, DeprecationDependency
from datetime import datetime

app = FastAPI()


# 1. Dependency Usage
@app.get("/dep-warning", dependencies=[Depends(DeprecationDependency())])
def dep_warning():
    return {"msg": "warning"}


@app.get(
    "/dep-sunset",
    dependencies=[Depends(DeprecationDependency(sunset_date=datetime(2000, 1, 1)))],
)
def dep_sunset():
    return {"msg": "gone"}


@app.get(
    "/dep-redirect",
    dependencies=[
        Depends(
            DeprecationDependency(sunset_date=datetime(2000, 1, 1), alternative="/new")
        )
    ],
)
def dep_redirect():
    return {"msg": "gone"}


# 2. Decorator Usage
@app.get("/dec-simple")
@deprecated()
def dec_simple():
    return {"msg": "simple"}


@app.get("/dec-args")
@deprecated(deprecation_date="2020-01-01")
def dec_args():
    return {"msg": "args"}


@app.get("/dec-explicit")
@deprecated()
def dec_explicit(request: Request, response: Response):
    return {"msg": "explicit"}


client = TestClient(app)


def test_dep_warning():
    response = client.get("/dep-warning")
    assert response.status_code == 200
    assert "Deprecation" in response.headers
    assert response.headers["Deprecation"].startswith("@")


def test_dep_sunset():
    response = client.get("/dep-sunset")
    assert response.status_code == 410


def test_dep_redirect():
    response = client.get("/dep-redirect", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["Location"] == "/new"


def test_dec_simple():
    response = client.get("/dec-simple")
    assert response.status_code == 200
    assert "Deprecation" in response.headers


def test_dec_args():
    response = client.get("/dec-args")
    assert response.status_code == 200
    assert "Deprecation" in response.headers
    # Check timestamp is roughly 2020-01-01 (1577836800)
    assert response.headers["Deprecation"] == "@1577836800"


def test_dec_explicit():
    response = client.get("/dec-explicit")
    assert response.status_code == 200
    assert "Deprecation" in response.headers
