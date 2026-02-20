# FastAPI Deprecation

<div align="center">
  <p align="center">
    <strong>RFC 9745 compliant API deprecation for FastAPI.</strong>
  </p>
</div>

---

**FastAPI Deprecation** helps you manage the lifecycle of your API endpoints using standard HTTP headers (`Deprecation`, `Sunset`, `Link`) and automated blocking logic. It allows you to gracefully warn clients about upcoming deprecations and automatically shut down endpoints when they reach their sunset date.

## Features

- **Standard Compliance**: Fully implements [RFC 9745](https://datatracker.ietf.org/doc/rfc9745/) and [RFC 8594](https://datatracker.ietf.org/doc/rfc8594/) with support for multiple link relations (`rel="alternate"`, `rel="successor-version"`, etc.).
- **Decorator-based & Middleware**: Simple `@deprecated` decorator for path operations, and `DeprecationMiddleware` for globally deprecating prefixes or intercepting 404s for sunset endpoints.
- **Automated Blocking**: Automatically returns `410 Gone` or `301 Moved Permanently` (or custom responses) after the `sunset_date`.
- **OpenAPI Integration**: Automatically modifies the Swagger UI/ReDoc to mark active deprecations and announces future upcoming deprecations.
- **Client-Side Caching**: Optionally injects `Cache-Control: max-age` to ensure warning responses aren't cached beyond the sunset date.
- **Extended Features**:
    - **Brownouts**: Schedule temporary shutdowns to simulate future removal.
    - **Telemetry**: Track usage of deprecated endpoints.
    - **Rate Limiting**: Hook into your favorite rate limiting library (e.g., `slowapi`) to dynamically throttle legacy traffic.

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

## Example Application
For a comprehensive demonstration of all features (Middleware, Router-level deprecation, mounted sub-apps, custom responses, and brownouts), check out the **Showcase Application** included in the repository:

```bash
uv run python examples/showcase.py
```
Open `http://localhost:8000/docs` to see the API lifecycle in action.

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

def log_usage(request: Request, response: Response, dep: Any):
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

### 5. Future Deprecation & Caching
You can announce a *future* deprecation date. The `Deprecation` header will still be sent, allowing clients to prepare. You can also inject `Cache-Control` headers so clients don't mistakenly cache warning responses past the sunset date.

```python
@deprecated(
    deprecation_date="2030-01-01",
    sunset_date="2031-01-01",
    inject_cache_control=True
)
async def future_proof(): ...
```

### 6. Custom Response Models & Multiple Links
Customize the HTTP 410/301 response payload dynamically using `response`, and provide extensive contextual documentation via multiple RFC 8594 `Link` relations.

```python
from starlette.responses import JSONResponse

custom_error = JSONResponse(
    status_code=410,
    content={"message": "This endpoint is permanently removed. Use v2."}
)

@deprecated(
    sunset_date="2024-01-01",
    response=custom_error,
    links={
        "alternate": "https://api.example.com/v2/items",
        "latest-version": "https://api.example.com/v3/items"
    }
)
async def custom_sunset(): ...
```

### 7. Global Middleware
Deprecate entire prefixes at the ASGI level, intercepting `404 Not Found` errors for removed routes and correctly returning `410 Gone` with deprecation metadata.

```python
from fastapi_deprecation import DeprecationMiddleware, DeprecationConfig

app.add_middleware(
    DeprecationMiddleware,
    deprecations={
        "/api/v1": DeprecationConfig(sunset_date="2025-01-01")
    }
)
```

Check the [API Reference](reference/core.md) for full details.
