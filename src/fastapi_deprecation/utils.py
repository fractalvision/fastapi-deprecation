from datetime import date, datetime, timezone
from email.utils import format_datetime
from typing import Union
import dateutil.parser

DateInput = Union[datetime, date, str, int, float]


def parse_date(value: DateInput) -> datetime:
    """
    Parse input into a timezone-aware UTC datetime object.

    Supports:
    - datetime (converted to UTC)
    - date (converted to UTC midnight)
    - str (parsed via dateutil, assumed UTC if allowed, or local if implied)
    - int/float (Unix timestamp)
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Assume UTC for naive to avoid "it works on my machine" issues.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        try:
            dt = dateutil.parser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise ValueError(f"Invalid date string: {value}")

    raise TypeError(f"Unsupported date type: {type(value)}")


def format_deprecation_date(value: DateInput) -> str:
    """
    Format date for 'Deprecation' header (RFC 9745).
    Format: @<timestamp> (RFC 9651 Date)
    """
    dt = parse_date(value)
    timestamp = int(dt.timestamp())
    return f"@{timestamp}"


def format_sunset_date(value: DateInput) -> str:
    """
    Format date for 'Sunset' header (RFC 8594).
    Format: HTTP-date (RFC 7231)
    """
    dt = parse_date(value)
    return format_datetime(dt, usegmt=True)
