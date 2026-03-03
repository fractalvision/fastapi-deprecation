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


def auto_deprecate_openapi(app: FastAPI, always_rebuild: bool = True):
    """
    Register the global exception handler for custom sunset responses.
    Overrides FastAPI's openapi() method to dynamically inject deprecation
    information on every request, ensuring that long-running apps
    correctly reflect state changes (warning -> sunset) over time.
    """
    app.add_exception_handler(DeprecationSunset, sunset_exception_handler)

    def extract_deps(target_app: FastAPI):
        deps = {}
        if hasattr(target_app, "user_middleware"):
            for mw in target_app.user_middleware:
                if mw.cls == DeprecationMiddleware:
                    mw_configs = mw.kwargs.get("deprecations", {})
                    for p, d in mw_configs.items():
                        deps[p] = d.config if hasattr(d, "config") else d
        return deps

    def wrap_app(
        target_app: FastAPI, prefix_for_globals: str, parent_global_deps: dict
    ):
        local_deps = extract_deps(target_app)
        combined_deps = {**parent_global_deps, **local_deps}

        original_openapi = target_app.openapi

        def custom_openapi():
            if not always_rebuild and getattr(
                target_app, "_custom_openapi_schema", None
            ):
                return target_app._custom_openapi_schema

            # Force FastAPI engine to build a fresh schema from the pristine routes
            target_app.openapi_schema = None
            openapi_schema = original_openapi()

            # Inject RFC compliance tags
            openapi_schema.setdefault("info", {})["x-rfc-compliance"] = [
                "RFC9745",
                "RFC8594",
            ]

            # Dynamically inject deprecations into the fresh schema
            _apply_dynamic_deprecations(
                target_app.routes,
                openapi_schema,
                prefix_for_globals=prefix_for_globals,
                global_deps=combined_deps,
            )

            if not always_rebuild:
                target_app._custom_openapi_schema = openapi_schema

            return openapi_schema

        target_app.openapi = custom_openapi

        # Find mounted sub-apps
        for route in target_app.routes:
            if isinstance(route, Mount) and isinstance(route.app, FastAPI):
                # Prepend the mount's path to the prefix for globals
                # so that router paths resolve correctly against middleware configurations
                new_prefix = prefix_for_globals + getattr(route, "path", "")
                wrap_app(route.app, new_prefix, combined_deps)

    wrap_app(app, "", extract_deps(app))


def _apply_dynamic_deprecations(
    routes, openapi_schema: dict, prefix_for_globals: str, global_deps: dict
):
    paths = openapi_schema.get("paths", {})
    for route in routes:
        if isinstance(route, APIRoute):
            route_path = prefix_for_globals + getattr(route, "path", "")

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

            # 4. Apply deprecation info to the generated schema dynamically
            if dep_info:
                now = datetime.now(timezone.utc)
                is_active_deprecation = True

                if dep_info.deprecation_date and dep_info.deprecation_date > now:
                    is_active_deprecation = False

                scheduled_brownouts = (
                    [
                        {"start": b[0].isoformat(), "end": b[1].isoformat()}
                        for b in dep_info.brownouts
                    ]
                    if dep_info.brownouts
                    else []
                )

                deprecation_date = (
                    dep_info.deprecation_date.isoformat()
                    if dep_info.deprecation_date
                    else None
                )
                sunset_date = (
                    dep_info.sunset_date.isoformat() if dep_info.sunset_date else None
                )
                is_sunset = dep_info.sunset_date and dep_info.sunset_date <= now
                chaotic_brownouts = (
                    dep_info.brownout_probability > 0 or dep_info.progressive_brownout
                )

                deprecation_meta = {
                    "deprecated": is_active_deprecation,
                    "deprecationDate": deprecation_date,
                    "sunsetDate": sunset_date,
                    "alternative": dep_info.alternative,
                    "link": dep_info.link,
                    "links": dep_info.links,
                    "phase": "warning" if not is_sunset else "sunset",
                    "scheduledBrownouts": scheduled_brownouts,
                    "chaoticBrownouts": chaotic_brownouts,
                    "detail": dep_info.detail,
                }

                # Exclude null values and empty collections to keep the OpenAPI schema clean
                deprecation_meta = {
                    k: v
                    for k, v in deprecation_meta.items()
                    if v is not None and not (isinstance(v, (list, dict)) and not v)
                }

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

                if dep_info.link:
                    warning_msg += f" See: {dep_info.link}."

                if dep_info.links:
                    links_str = ", ".join(dep_info.links.values())
                    warning_msg += f" See also: {links_str}."

                # Find the route operation in the schema to mutate it
                path_key = route.path_format
                for method in route.methods:
                    method_str = method.lower()
                    if path_key in paths and method_str in paths[path_key]:
                        operation = paths[path_key][method_str]

                        if is_active_deprecation:
                            operation["deprecated"] = True

                        operation["x-fastapi-deprecation"] = deprecation_meta

                        existing_desc = operation.get("description", "")
                        if warning_msg not in existing_desc:
                            if existing_desc:
                                operation["description"] = (
                                    existing_desc + f"\n\n{warning_msg}"
                                )
                            else:
                                operation["description"] = warning_msg
