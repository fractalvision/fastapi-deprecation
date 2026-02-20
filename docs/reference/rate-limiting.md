# Rate Limiting Integration

While `fastapi-deprecation` does not ship with a built-in rate limiter, it is designed to be easily combined with popular tools like `slowapi`.

A common pattern for API evolution is to **progressively throttle** traffic to deprecated endpoints to encourage users to migrate *before* the permanent sunset date.

## Integrating with `slowapi`

You can use the metadata injected by the `@deprecated` decorator inside a custom dynamic limit function to automatically adjust rate limits for deprecated endpoints.

### Example: Dynamic Throttling

`slowapi` allows the `limit` parameter to be a callable that returns a rate limit string. We can write a function that inspects the current FastAPI route for deprecation metadata and returns a stricter limit if it's deprecated.

```python
from fastapi import FastAPI, Request
from fastapi_deprecation import deprecated
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

def get_dynamic_limit(request: Request) -> str:
    """
    Dynamically calculate rate limits based on deprecation status.
    Returns "5/minute" if deprecated, otherwise "100/minute".
    """
    route = request.scope.get("route")
    if route and hasattr(route, "endpoint"):
        # The @deprecated decorator attaches __deprecation__ to the endpoint
        dep_info = getattr(route.endpoint, "__deprecation__", None)
        if dep_info:
            # We could even check dep_info.deprecation_date to only
            # throttle if the deprecation date has passed!
            return "5/minute"

    return "100/minute"

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/old-endpoint")
@deprecated(sunset_date="2025-12-31")
@limiter.limit(get_dynamic_limit)
async def old_endpoint(request: Request):
    return {"message": "Please migrate. You are strictly rate limited."}

@app.get("/new-endpoint")
@limiter.limit(get_dynamic_limit)
async def new_endpoint(request: Request):
    return {"message": "Welcome to the future. You have standard limits."}
```

### Advanced: Global Dependency Throttling

A more idiomatic way to apply a dynamic limit across a whole `FastAPI` instance or `APIRouter` without middleware is to use a global dependency block and inject the `Limiter` directly into it. SlowAPI requires the `@limiter.limit()` decorator on actual endpoints for its interceptor to work natively, but you can build a custom dependency that executes the rate check.

```python
from fastapi import FastAPI, Request, HTTPException, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

async def check_global_rate_limit(request: Request):
    # Determine the limit based on whether the endpoint is deprecated
    limit = "100/minute"
    route = request.scope.get("route")
    if route and hasattr(route, "endpoint"):
        if getattr(route.endpoint, "__deprecation__", None):
            limit = "5/minute"

    # Manually check the limiter
    # (Note: This is an advanced pattern if you don't use @limiter.limit decorators)
    try:
        limiter._check_request_limit(request, None, limit, True)
    except Exception as e:
         raise HTTPException(status_code=429, detail="Rate limit exceeded")

# Apply globally to all endpoints
app = FastAPI(dependencies=[Depends(check_global_rate_limit)])

@app.get("/old-endpoint")
@deprecated(sunset_date="2025-12-31")
async def old_endpoint():
    return {"message": "You only get 5 calls per minute here."}
```
### Advanced: Global Middleware Throttling (For Mounted Sub-Apps)

A limitation of the dependency approach above is that FastAPI dependencies **do not propagate** to mounted sub-applications (`app.mount("/sub", sub_app)`).

If you have a complex architecture with multiple mounted ASGI apps and you want a single global choke-point for rate limits, an ASGI Middleware is required. Middleware wraps the entire application before routing occurs.

```python
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_deprecation import deprecated

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class ProgressiveThrottlingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, fallback_limit: str = "100/minute", deprecated_limit: str = "5/minute"):
        super().__init__(app)
        self.fallback_limit = fallback_limit
        self.deprecated_limit = deprecated_limit

    async def dispatch(self, request: Request, call_next):
        limit_to_apply = self.fallback_limit

        # In middleware, we manually inspect the routes to find the deprecation metadata
        # Note: For mounted apps, you might need to recursively search `request.app.routes`
        # if the sub-app is deeply nested.
        for route in request.app.routes:
            if isinstance(route, APIRoute):
                match, scope = route.matches(request.scope)
                if match == match.FULL:
                    dep_info = getattr(route.endpoint, "__deprecation__", None)
                    if dep_info:
                        limit_to_apply = self.deprecated_limit
                    break

        # Execute your rate limiter logic here using `limit_to_apply`

        return await call_next(request)

app.add_middleware(ProgressiveThrottlingMiddleware)
```

By keeping the core lightweight, `fastapi-deprecation` gives you the freedom to wire these sunset phases into whichever API Gateway or internal logic your infrastructure demands.
