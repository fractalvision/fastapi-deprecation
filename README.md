# FastAPI Deprecation

<div align="center">
  <p align="center">
    <strong>RFC 9745 compliant API deprecation for FastAPI.</strong>
  </p>
</div>

---

**FastAPI Deprecation** helps you manage the lifecycle of your API endpoints using standard HTTP headers (`Deprecation`, `Sunset`, `Link`) and automated blocking logic. It allows you to gracefully warn clients about upcoming deprecations and automatically shut down endpoints when they reach their sunset date.

## Features

- **Standard Compliance**: Fully implements [RFC 9745](https://datatracker.ietf.org/doc/rfc9745/) and [RFC 8594](https://datatracker.ietf.org/doc/rfc8594/).
- **Decorator-based**: Simple `@deprecated` decorator for your path operations.
- **Automated Blocking**: Automatically returns `410 Gone` or `301 Moved Permanently` after the `sunset_date`.
- **OpenAPI Integration**: Automatically marks endpoints as deprecated in Swagger UI and ReDoc.
- **Router Support**: Deprecate entire routers or sub-applications with `DeprecationDependency`.
- **Extended Features**:
    - **Telemetry**: Track usage of deprecated endpoints.
    - **Brownouts**: Schedule temporary shutdowns to simulate future removal.
    - **Future Deprecation**: Announce upcoming deprecations before they become active.

## Installation

```bash
pip install fastapi-deprecation
# or with uv
uv add fastapi-deprecation
```

## Quick Start

```python
from fastapi import FastAPI
from fastapi_deprecation import deprecated, auto_deprecate_openapi

app = FastAPI()

@app.get("/old-endpoint")
@deprecated(
    deprecation_date="2024-01-01",
    sunset_date="2025-01-01",
    alternative="/new-endpoint",
    detail="This endpoint is old and tired."
)
async def old():
    return {"message": "Enjoy it while it lasts!"}

# Don't forget to update the schema at the end!
auto_deprecate_openapi(app)
```

## How It Works

1.  **Warning Phase** (Before Sunset):
    *   Requests return `200 OK`.
    *   Response headers include:
        *   `Deprecation: @1704067200` (Unix timestamp of `deprecation_date`)
        *   `Sunset: Wed, 01 Jan 2025 00:00:00 GMT`
        *   `Link: </new-endpoint>; rel="alternative"`

2.  **Blocking Phase** (After Sunset):
    *   Requests return `410 Gone` (or `301 Moved Permanently` if `alternative` is set).
    *   The `detail` message is returned in the response body.

## Advanced Usage

See the [Documentation](https://example.com/docs) for full details on API reference and advanced configuration.
