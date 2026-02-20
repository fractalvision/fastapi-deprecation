# OpenAPI Integration API

This module handles the modification of the OpenAPI (Swagger) schema to reflect the deprecation status of your endpoints.

## Automatic Schema Updates

FastAPI does not automatically set `deprecated: true` in OpenAPI based on your custom decorators. This module fills that gap.

Call `auto_deprecate_openapi(app)` *after* you have defined all your routes.

```python
from fastapi import FastAPI
from fastapi_deprecation import deprecated, auto_deprecate_openapi

app = FastAPI()

@app.get("/old")
@deprecated(deprecation_date="2020-01-01")
def old(): ...

# Must call this after routes are defined!
auto_deprecate_openapi(app)
```

### Recursive Support

The function automatically detects mounted sub-applications (using `app.mount()`) and updates their OpenAPI definitions recursively.

### Upcoming Deprecations

If the endpoint has a `deprecation_date` that is in the future, the library will **not** set `deprecated: true` yet (as the endpoint is still fully active). However, it will append an `**UPCOMING DEPRECATION**` warning to the endpoint's description so clients can prepare. Once the date passes, `deprecated: true` is automatically applied.

## Reference

::: fastapi_deprecation.openapi
    options:
      show_root_heading: true
      show_source: true
