from datetime import datetime, timedelta, timezone
import logging

from fastapi import FastAPI, APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi_deprecation import (
    deprecated,
    DeprecationDependency,
    DeprecationMiddleware,
    DeprecationConfig,
    auto_deprecate_openapi,
    set_deprecation_callback,
)

# ---------------------------------------------------------
# Setup: Telemetry Logging
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api.telemetry")


def log_deprecation_usage(
    request: Request, response: Response, dep: DeprecationDependency | DeprecationConfig
):
    """Log when a client accesses a deprecated endpoint."""
    logger.warning(
        f"DEPRECATED USAGE: Client accessed {request.url.path} "
        f"(Sunset: {dep.sunset_date})"
    )


set_deprecation_callback(log_deprecation_usage)

# Calculate some dynamic dates for the example so it always runs
now = datetime.now(timezone.utc)
sunset_past = now - timedelta(days=30)
sunset_future = now + timedelta(days=60)
deprecation_future = now + timedelta(days=10)

# =========================================================
# Scenario 1: Mounted Sub-Application (v1 API)
# Uses Global Middleware to sunset entire prefix
# =========================================================
v1_app = FastAPI(title="Showcase API v1", description="Legacy API (Sunset)")


@v1_app.get("/users")
async def get_users_v1():
    # Because of middleware, you won't actually be able to hit this if sunset_date has passed
    return [{"id": 1, "name": "Alice", "v": 1}, {"id": 2, "name": "Bob", "v": 1}]


@v1_app.get("/products")
async def get_products_v1():
    return [{"id": 101, "name": "Widget", "v": 1}]


# =========================================================
# Scenario 2: Router Dependency (v2 API)
# Deprecates all endpoints within a router
# =========================================================
v2_router = APIRouter(
    prefix="/v2",
    tags=["v2 - Deprecated Layer"],
    dependencies=[
        Depends(
            DeprecationDependency(
                deprecation_date="2024-01-01",
                sunset_date=sunset_future.isoformat(),
                alternative="/v3",
                links={"successor-version": "/docs#/v3"},
            )
        )
    ],
)


@v2_router.get("/users")
async def get_users_v2(active_only: bool = True):
    """Old user fetching logic. Still active, but emits warnings."""
    return [
        {"id": 1, "name": "Alice", "schema": "v2"},
        {"id": 2, "name": "Bob", "schema": "v2"},
    ]


@v2_router.get("/products")
async def get_products_v2():
    return [{"id": 101, "name": "Super Widget", "schema": "v2"}]


# =========================================================
# Scenario 3: Decorator (v3 API)
# Granular endpoint deprecations and the active modern API
# =========================================================
v3_router = APIRouter(prefix="/v3", tags=["v3 - Current API"])


# A fully active, modern endpoint
@v3_router.get("/users")
async def get_users_v3(status: str = Query("active", description="Filter by status")):
    return {
        "data": [
            {"id": 1, "name": "Alice", "status": "active", "schema": "v3"},
            {"id": 2, "name": "Bob", "status": "active", "schema": "v3"},
        ],
        "meta": {"version": 3, "total": 2},
    }


# An endpoint undergoing a scheduled brownout
@v3_router.get("/reports/legacy")
@deprecated(
    sunset_date=sunset_future.isoformat(),
    alternative="/v3/reports/modern",
    brownouts=[
        (now - timedelta(hours=1), now + timedelta(hours=2))  # Currently offline!
    ],
    detail="Legacy reports are undergoing scheduled maintenance (brownout) to simulate final shutdown.",
)
async def legacy_reports():
    return {"report_data": "Lots of unstructured data in a bad format"}


# An endpoint using a Custom Response Model
custom_sunset_response = JSONResponse(
    status_code=410,
    content={
        "error": "gone",
        "description": "The XML export feature has been permanently removed.",
        "migration_guide": "https://example.com/migrate-from-xml",
    },
)


@v3_router.get("/export/xml")
@deprecated(
    sunset_date=sunset_past.isoformat(),  # Sunset has already passed!
    response=custom_sunset_response,
)
async def export_xml():
    return "<data><item>You should not see this</item></data>"


# An endpoint announcing an Upcoming Deprecation
@v3_router.get("/legacy-auth")
@deprecated(
    deprecation_date=deprecation_future.isoformat(),  # Not deprecated yet, but will be!
    sunset_date=(now + timedelta(days=365)).isoformat(),
    detail="Switch to OAuth2 soon.",
)
async def legacy_auth():
    return {"token": "insecure-legacy-token"}


# An endpoint demonstrating Chaos Engineering and Edge Caching
@v3_router.get("/flaky-data")
@deprecated(
    deprecation_date=(
        now - timedelta(days=15)
    ).isoformat(),  # Deprecation started 15 days ago
    sunset_date=(now + timedelta(days=15)).isoformat(),  # Sunset is 15 days from now
    progressive_brownout=True,  # 50% failure rate right now!
    brownout_probability=0.1,  # Static fallback
    cache_tag="api-v3-flaky",  # Edge caching tag for instant CDN purging
    detail="This endpoint is progressively degrading. Expect probabilistic 410 Gone responses.",
)
async def flaky_data():
    return {"message": "You got lucky! The request succeeded."}


# =========================================================
# Main Application Assembly
# =========================================================
app = FastAPI(
    title="Deprecation Showcase API",
    description="Demonstrates global middleware, router dependencies, and granular `@deprecated` decorators.",
)

# 1. Apply Middleware (applies to the mounted v1 app and unroutable 404s)
app.add_middleware(
    DeprecationMiddleware,
    deprecations={
        "/v1": DeprecationConfig(
            sunset_date=sunset_past,  # v1 is globally killed by middleware
            detail="The v1 API is sunset globally via ASGI middleware.",
        )
    },
)

# 2. Mount Sub-App
app.mount("/v1", v1_app)

# 3. Include Routers
app.include_router(v2_router)
app.include_router(v3_router)

# 4. Generate OpenAPI schemas for all endpoints (including mounts!)
auto_deprecate_openapi(app)

if __name__ == "__main__":
    import uvicorn

    print("\n--- Starting FastAPI Deprecation Showcase ---")
    print("API documentation serving at: http://127.0.0.1:8000/docs")
    print("Check out the /v1, /v2, and /v3 endpoints in the Swagger interface.\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
