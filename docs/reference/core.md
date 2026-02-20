# Core API

The `core` module provides the primary interface for deprecating endpoints in FastAPI: the `@deprecated` decorator.

## Usage

The `@deprecated` decorator should be placed *above* your path operation function but *below* the FastAPI router decorator (though order usually doesn't matter for functionality, it keeps the code clean).

```python
from fastapi import FastAPI
from fastapi_deprecation import deprecated

app = FastAPI()

@app.get("/items")
@deprecated(
    deprecation_date="2024-01-01",
    sunset_date="2025-01-01",
    alternative="/new_items",
    links={"latest-version": "https://api.example.com/v3"},
    inject_cache_control=True
)
async def read_items():
    return [{"item_id": "Foo"}]
```

## Reference

::: fastapi_deprecation.core
    options:
      show_root_heading: true
      show_source: true
