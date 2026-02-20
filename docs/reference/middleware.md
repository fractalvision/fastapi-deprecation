# Middleware

The `middleware` module provides the `DeprecationMiddleware` class, an ASGI middleware allowing users to deprecate entire application prefixes dynamically without relying on static decorators or router dependencies.

This is especially useful for quickly deprecating or sunsetting sweeping sections of an API by routing arbitrary path prefixes (e.g. `/v1`), issuing global HTTP overrides (like `410 Gone`), and unifying `Deprecation` headers for all matching requests.

::: fastapi_deprecation.middleware
    options:
        members:
            - DeprecationMiddleware
