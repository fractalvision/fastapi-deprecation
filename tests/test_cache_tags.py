from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_deprecation import deprecated
from datetime import datetime, timezone, timedelta

app = FastAPI()

now = datetime.now(timezone.utc)
future_sunset = now + timedelta(days=365)


@app.get("/tagged")
@deprecated(
    deprecation_date=now - timedelta(days=1),
    sunset_date=future_sunset,
    cache_tag="api-v1-deprecation",
)
async def tagged_endpoint():
    return {"message": "tagged"}


client = TestClient(app)


def test_cache_tags_injected():
    response = client.get("/tagged")
    assert response.status_code == 200
    assert "Cache-Tag" in response.headers
    assert response.headers["Cache-Tag"] == "api-v1-deprecation"
    assert "Surrogate-Key" in response.headers
    assert response.headers["Surrogate-Key"] == "api-v1-deprecation"
