from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_deprecation import deprecated, auto_deprecate_openapi

app = FastAPI()


@app.get("/normal")
def normal():
    return {}


@app.get("/deprecated")
@deprecated(deprecation_date="2022-01-01", alternative="/new")
def deprecated_route():
    return {}


@app.get("/deprecated-nodate")
@deprecated()
def deprecated_nodate():
    return {}


# Apply schema modifications
auto_deprecate_openapi(app)

client = TestClient(app)


def test_openapi_schema():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    # Check normal route
    assert not schema["paths"]["/normal"]["get"].get("deprecated", False)

    # Check deprecated route
    dep_op = schema["paths"]["/deprecated"]["get"]
    assert dep_op["deprecated"] is True
    assert "Deprecated since" in dep_op["description"]
    assert "Alternative: /new" in dep_op["description"]

    # Check nodate
    nodate_op = schema["paths"]["/deprecated-nodate"]["get"]
    assert nodate_op["deprecated"] is True
    assert "**DEPRECATED**" in nodate_op.get("description", "")
