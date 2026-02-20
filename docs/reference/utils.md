# Utils API

This module contains helper functions for parsing dates and formatting HTTP headers.

## Date Parsing

The library supports multiple date formats via the `DateInput` type alias:

1.  **ISO 8601 Strings**: `"2024-01-01"`, `"2024-01-01T12:00:00Z"`
2.  **Date/Datetime Objects**: `datetime.date(2024, 1, 1)`, `datetime.datetime(2024, 1, 1, 12, 0, 0)`
3.  **Integers/Floats**: Unix timestamps

All dates are internally converted to UTC timestamps for the `Deprecation` header (as per RFC 9745) and HTTP-date format for the `Sunset` header.

## Reference

::: fastapi_deprecation.utils
    options:
      show_root_heading: true
      show_source: true
