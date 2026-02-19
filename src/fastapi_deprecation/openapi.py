from fastapi import FastAPI
from fastapi.routing import APIRoute


def auto_deprecate_openapi(app: FastAPI):
    """
    Iterate over all routes in the FastAPI application.
    If a route's endpoint is marked with @deprecated, update its OpenAPI definition:
    - Set 'deprecated' to True.
    - Append deprecation warning to the description.
    """
    for route in app.routes:
        if isinstance(route, APIRoute):
            # Check if the endpoint function has the __deprecation__ attribute
            # This is set by the @deprecated decorator wrapper
            dep_info = getattr(route.endpoint, "__deprecation__", None)

            if dep_info:
                # Mark as deprecated in OpenAPI
                route.deprecated = True

                # Setup description message
                warning_msg = " **DEPRECATED**"
                if dep_info.deprecation_date:
                    dt_str = dep_info.deprecation_date.isoformat()
                    warning_msg += f". Deprecated since {dt_str}."

                if dep_info.sunset_date:
                    sunset_str = dep_info.sunset_date.isoformat()
                    warning_msg += f" Sunset date: {sunset_str}."

                if dep_info.alternative:
                    warning_msg += f" Alternative: {dep_info.alternative}."

                if dep_info.link:
                    warning_msg += f" See: {dep_info.link}."

                # Append to existing description
                if route.description:
                    route.description += f"\n\n{warning_msg}"
                else:
                    route.description = warning_msg
