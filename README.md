# FastAPI Deprecation

<div align="center">
  <p align="center">
    <strong>RFC 9745 compliant API deprecation for FastAPI.</strong>
  </p>
  <p align="center">
    <a href="https://github.com/fractalvision/fastapi-deprecation/actions/workflows/test.yml">
      <img src="https://github.com/fractalvision/fastapi-deprecation/actions/workflows/test.yml/badge.svg" alt="Test Status"/>
    </a>
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

## Documentation

To run the documentation locally:

```bash
uv run zensical serve
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

### 1. Brownouts (Scheduled Unavailability)
You can simulate future shutdowns by scheduling "brownouts" — temporary periods where the endpoint returns `410 Gone` (or `301` if alternative is set). This forces clients to notice the deprecation before the final sunset.

```python
@deprecated(
    sunset_date="2025-12-31",
    brownouts=[
        # 1-hour brownout
        ("2025-11-01T09:00:00Z", "2025-11-01T10:00:00Z"),
        # 1-day brownout
        ("2025-12-01T00:00:00Z", "2025-12-02T00:00:00Z"),
    ],
    detail="Service is temporarily unavailable due to scheduled brownout."
)
async def my_endpoint(): ...
```

### 2. Telemetry & Logging
Track usage of deprecated endpoints using a global callback. This is useful for monitoring which clients are still using old APIs.

```python
import logging
from fastapi import Request, Response
from fastapi_deprecation import set_deprecation_callback, DeprecationDependency

logger = logging.getLogger("deprecation")

def log_usage(request: Request, response: Response, dep: DeprecationDependency):
    logger.warning(
        f"Deprecated endpoint {request.url} accessed. "
        f"Deprecation date: {dep.deprecation_date}"
    )

set_deprecation_callback(log_usage)
```

### 3. Deprecating Entire Routers
To deprecate a whole group of endpoints, use `DeprecationDependency` on the `APIRouter`.

```python
from fastapi import APIRouter, Depends
from fastapi_deprecation import DeprecationDependency

router = APIRouter(
    dependencies=[Depends(DeprecationDependency(deprecation_date="2024-01-01"))]
)

@router.get("/sub-route")
async def sub(): ...
```

### 4. Recursive OpenAPI Support
When using `auto_deprecate_openapi(app)`, it automatically traverses potentially mounted sub-applications (`app.mount(...)`) and marks their routes as deprecated if configured.

```python
root_app.mount("/v1", v1_app)
# This will update OpenAPI for both root_app AND v1_app
auto_deprecate_openapi(root_app)
```

### 5. Future Deprecation
You can announce a *future* deprecation date. The `Deprecation` header will still be sent (as per RFC 9745), allowing clients to prepare in advance.

```python
@deprecated(deprecation_date="2030-01-01")
async def future_proof(): ...
```

See the [Documentation](https://example.com/docs) for full details on API reference and advanced configuration.
