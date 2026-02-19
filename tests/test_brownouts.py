from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_deprecation import deprecated

app = FastAPI()


# Brownout windows:
# 1. 2025-01-01 10:00 - 12:00
# 2. 2025-01-02 10:00 - 12:00
@app.get("/brownout")
@deprecated(
    brownouts=[
        ("2025-01-01T10:00:00Z", "2025-01-01T12:00:00Z"),
        ("2025-01-02T10:00:00Z", "2025-01-02T12:00:00Z"),
    ],
    detail="Service is in a scheduled brownout.",
)
def brownout_route():
    return {"msg": "ok"}


client = TestClient(app)


def test_brownout_active():
    # Inside window 1
    mock_now = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    with patch("fastapi_deprecation.dependencies.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = datetime

        response = client.get("/brownout")
        assert response.status_code == 410
        assert response.json()["detail"] == "Service is in a scheduled brownout."


def test_brownout_inactive():
    # Before window 1
    mock_now = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
    with patch("fastapi_deprecation.dependencies.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = datetime

        response = client.get("/brownout")
        assert response.status_code == 200
        assert response.json() == {"msg": "ok"}

    # Between windows
    mock_now_between = datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    with patch("fastapi_deprecation.dependencies.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now_between
        mock_dt.side_effect = datetime

        response = client.get("/brownout")
        assert response.status_code == 200


def test_brownout_custom_detail():
    # Test detail override
    mock_now = datetime(2025, 1, 2, 11, 0, 0, tzinfo=timezone.utc)  # Inside window 2
    with patch("fastapi_deprecation.dependencies.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = datetime

        response = client.get("/brownout")
        assert response.status_code == 410
        assert response.json()["detail"] == "Service is in a scheduled brownout."
