import pytest
from datetime import datetime, timezone
from fastapi_deprecation.utils import format_deprecation_date, format_sunset_date


def test_format_deprecation_date_timestamp():
    # Thursday, 12 October 2023 10:00:00 UTC = 1697104800
    dt_int = 1697104800
    formatted = format_deprecation_date(dt_int)
    assert formatted == "@1697104800"


def test_format_deprecation_date_datetime_utc():
    # Thursday, 12 October 2023 10:00:00 UTC
    dt = datetime(2023, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    formatted = format_deprecation_date(dt)
    assert formatted == "@1697104800"


def test_format_deprecation_date_datetime_naive():
    # Naive is assumed UTC
    dt = datetime(2023, 10, 12, 10, 0, 0)
    formatted = format_deprecation_date(dt)
    # 1697104800 if interpreted as UTC
    # Since utils.py implementation: if tzinfo is None: return value.replace(tzinfo=timezone.utc)
    # So 1697104800 is correct.
    assert formatted == "@1697104800"


def test_format_deprecation_date_str():
    dt_str = "2023-10-12T10:00:00Z"
    formatted = format_deprecation_date(dt_str)
    assert formatted == "@1697104800"


def test_format_sunset_date_http_date():
    # Thursday, 12 October 2023 10:00:00 UTC
    dt = datetime(2023, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    formatted = format_sunset_date(dt)
    # Expected HTTP-date format: Thu, 12 Oct 2023 10:00:00 GMT
    assert formatted == "Thu, 12 Oct 2023 10:00:00 GMT"


def test_parse_date_invalid_str():
    with pytest.raises(ValueError):
        format_deprecation_date("invalid-date-string")
