from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import Mount


from datetime import datetime, timezone

from .dependencies import DeprecationSunset, sunset_exception_handler


def auto_deprecate_openapi(app: FastAPI):
    """
    Register the global exception handler for custom sunset responses.
    Iterate over all routes in the FastAPI application.
    If a route's endpoint is marked with @deprecated, update its OpenAPI definition.
    """
    app.add_exception_handler(DeprecationSunset, sunset_exception_handler)
    for route in app.routes:
        if isinstance(route, Mount):
            # Recursively check mounted apps
            if isinstance(route.app, FastAPI):
                auto_deprecate_openapi(route.app)
        elif isinstance(route, APIRoute):
            # Check if the endpoint function has the __deprecation__ attribute
            # This is set by the @deprecated decorator wrapper
            dep_info = getattr(route.endpoint, "__deprecation__", None)

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
                    route.description += f"\n\n{warning_msg}"
                else:
                    route.description = warning_msg
