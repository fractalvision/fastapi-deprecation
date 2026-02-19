from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from fastapi_deprecation import (
    deprecated,
    set_deprecation_callback,
    DeprecationDependency,
)

app = FastAPI()


# Future deprecation
@app.get("/future")
@deprecated(deprecation_date="2030-01-01")
def future_deprecation():
    return {"msg": "future"}


# Telemetry test
callback_hits = []


def telemetry_callback(
    request: Request, response: Response, dep: DeprecationDependency
):
    callback_hits.append({"path": request.url.path, "detail": dep.deprecation_date})


set_deprecation_callback(telemetry_callback)


@app.get("/telemetry")
@deprecated(deprecation_date="2020-01-01")
def telemetry_route():
    return {"msg": "telemetry"}


client = TestClient(app)


def test_future_deprecation():
    response = client.get("/future")
    assert response.status_code == 200
    # RFC 9745: Must send header even if date is in future
    assert "Deprecation" in response.headers
    # The date should be parsed and formatted correctly (timestamp)
    assert response.headers["Deprecation"].startswith("@")


def test_telemetry():
    callback_hits.clear()
    response = client.get("/telemetry")
    assert response.status_code == 200
    assert len(callback_hits) == 1
    assert callback_hits[0]["path"] == "/telemetry"
    assert callback_hits[0]["detail"] is not None
