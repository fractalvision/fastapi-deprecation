from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import Mount

from datetime import datetime, timezone

from .dependencies import (
    DeprecationSunset,
    sunset_exception_handler,
    DeprecationDependency,
)
from .middleware import DeprecationMiddleware


def auto_deprecate_openapi(app: FastAPI):
    """
    Register the global exception handler for custom sunset responses.
    Iterate over all routes in the FastAPI application.
    Updates OpenAPI definition for endpoints marked via @deprecated, router Depends(), or global middleware.
    """
    app.add_exception_handler(DeprecationSunset, sunset_exception_handler)

    # Extract global middleware deprecations to apply to routes
    global_deps = {}
    if hasattr(app, "user_middleware"):
        for mw in app.user_middleware:
            if mw.cls == DeprecationMiddleware:
                mw_configs = mw.kwargs.get("deprecations", {})
                for p, d in mw_configs.items():
                    global_deps[p] = d.config if hasattr(d, "config") else d

    _deprecate_routes(app, prefix="", global_deps=global_deps)


def _deprecate_routes(app: FastAPI, prefix: str, global_deps: dict):
    for route in app.routes:
        route_path = prefix + getattr(route, "path", "")

        if isinstance(route, Mount):
            if isinstance(route.app, FastAPI):
                _deprecate_routes(route.app, prefix=route_path, global_deps=global_deps)

        elif isinstance(route, APIRoute):
            # 1. Check Decorator
            dep_info = getattr(route.endpoint, "__deprecation__", None)

            # 2. Check Router Dependencies
            if not dep_info and hasattr(route, "dependencies"):
                for dep in route.dependencies:
                    if hasattr(dep, "dependency") and isinstance(
                        dep.dependency, DeprecationDependency
                    ):
                        dep_info = dep.dependency.config
                        break

            # 3. Check Global Middleware
            if not dep_info:
                matched_prefix = ""
                for p, d in global_deps.items():
                    if route_path.startswith(p) and len(p) > len(matched_prefix):
                        matched_prefix = p
                        dep_info = d

            if dep_info:
                now = datetime.now(timezone.utc)
                is_active_deprecation = True

                if dep_info.deprecation_date and dep_info.deprecation_date > now:
                    is_active_deprecation = False

                if is_active_deprecation:
                    route.deprecated = True

                # Setup description message
                if not is_active_deprecation:
                    warning_msg = " **UPCOMING DEPRECATION**"
                else:
                    warning_msg = " **DEPRECATED**"

                if dep_info.deprecation_date:
                    dt_str = dep_info.deprecation_date.isoformat()
                    warning_msg += f". Deprecated since {dt_str}."

                if dep_info.sunset_date:
                    sunset_str = dep_info.sunset_date.isoformat()
                    warning_msg += f" Sunset date: {sunset_str}."

                if dep_info.alternative:
                    warning_msg += f" Alternative: {dep_info.alternative}."

                if dep_info.links:
                    links_str = ", ".join(dep_info.links.values())
                    warning_msg += f" See: {links_str}."

                # Append to existing description
                if route.description:
                    if warning_msg not in route.description:
                        route.description += f"\n\n{warning_msg}"
                else:
                    route.description = warning_msg
