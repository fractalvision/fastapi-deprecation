# Dependencies API

The `dependencies` module contains the underlying logic for handling deprecation lifecycles. It allows for more advanced usage patterns, such as applying deprecation to entire routers or registering global callbacks.

## Router Deprecation

You can deprecate an entire `APIRouter` by adding `DeprecationDependency` to its dependencies list.

```python
from fastapi import APIRouter, Depends
from fastapi_deprecation import DeprecationDependency

router = APIRouter(
    dependencies=[
        Depends(DeprecationDependency(deprecation_date="2024-06-01"))
    ]
)
```



::: fastapi_deprecation.dependencies
    options:
      show_root_heading: true
      show_source: true
