from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_deprecation import deprecated
from datetime import datetime, timezone, timedelta

app = FastAPI()

now = datetime.now(timezone.utc)
dep_date = now - timedelta(days=5)
sunset_date = now + timedelta(days=5)


@app.get("/static-brownout")
@deprecated(
    deprecation_date=dep_date,
    sunset_date=sunset_date,
    brownout_probability=0.5,
)
async def static_brownout():
    return {"message": "success"}


@app.get("/progressive-brownout")
@deprecated(
    deprecation_date=dep_date,
    sunset_date=sunset_date,
    progressive_brownout=True,
)
async def progressive_brownout():
    return {"message": "success"}


client = TestClient(app)


def test_static_brownout_success():
    with patch("random.random", return_value=0.6):
        response = client.get("/static-brownout")
        assert response.status_code == 200


def test_static_brownout_failure():
    with patch("random.random", return_value=0.4):
        response = client.get("/static-brownout")
        assert response.status_code == 410


def test_progressive_brownout_success():
    # We are exactly 50% through the life cycle (5 days past dep, 5 days until sunset).
    # Probability should be 0.5. A random of 0.6 should result in success.
    with patch("random.random", return_value=0.6):
        response = client.get("/progressive-brownout")
        assert response.status_code == 200


def test_progressive_brownout_failure():
    # Probability is 0.5. A random of 0.4 should result in failure.
    with patch("random.random", return_value=0.4):
        response = client.get("/progressive-brownout")
        assert response.status_code == 410


def test_validation_mutually_exclusive():
    import pytest
    from fastapi_deprecation import DeprecationDependency

    with pytest.raises(
        ValueError,
        match="Cannot use both static brownout_probability and progressive_brownout",
    ):
        DeprecationDependency(
            brownout_probability=0.5,
            progressive_brownout=True,
        )


def test_validation_progressive_requirements():
    import pytest
    from fastapi_deprecation import DeprecationDependency

    with pytest.raises(
        ValueError,
        match="progressive_brownout requires both deprecation_date and sunset_date",
    ):
        DeprecationDependency(
            progressive_brownout=True,
            # Missing dates!
        )


def test_validation_probability_bounds():
    import pytest
    from fastapi_deprecation import DeprecationDependency

    with pytest.raises(
        ValueError, match="brownout_probability must be between 0.0 and 1.0"
    ):
        DeprecationDependency(
            brownout_probability=1.5,
        )

    with pytest.raises(
        ValueError, match="brownout_probability must be between 0.0 and 1.0"
    ):
        DeprecationDependency(
            brownout_probability=-0.1,
        )
