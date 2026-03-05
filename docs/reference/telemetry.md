# Universal Metrics & Telemetry

While a simple `logger.warning` is often sufficient for basic observability, production migrations often require concrete analytics to accurately track how many clients are still hitting deprecated routes or failing during brownouts.

`fastapi-deprecation` includes a built-in `DeprecationTracker` powered by a universal metrics architecture. It seamlessly binds to the execution pipeline to record and categorize route traffic by HTTP method, URL path, and deprecation phase (`warn` vs `block`), while safely exporting schedule metadata (like `sunset_date`).

## Single-Worker (InMemory)

The default `InMemoryMetricsStore` aggregates metrics locally using a standard dictionary. This is perfectly suitable for local development or single-worker deployments (e.g. AWS Lambda / simple standard setups).

```python
from fastapi import FastAPI
from fastapi_deprecation import set_deprecation_callback
from fastapi_deprecation.metrics import DeprecationTracker, InMemoryMetricsStore

app = FastAPI()

# 1. Initialize tracker explicitly
tracker = DeprecationTracker(store=InMemoryMetricsStore())

# 2. Hook into the deprecation engine
set_deprecation_callback(tracker.record_usage)

# 3. Expose the analytics to your business dashboard
@app.get("/admin/metrics/deprecation")
async def get_metrics():
    # Returns a JSON dictionary of all deprecation traffic
    return await tracker.export_json()
```

## Multi-Worker / Enterprise Plugins

If you deploy your API using `gunicorn` or `uvicorn --workers N`, your Python application runs across completely isolated processes. If you use the `InMemoryMetricsStore`, each worker process will maintain its own isolated counters.

To solve this, `fastapi-deprecation` offers extension plugins that connect to enterprise aggregators.

### Redis Synchronized Analytics

The Redis backend uses atomic `HINCRBY` operations to perfectly synchronize metrics globally across an infinite number of workers.

**Installation:**
```bash
pip install "fastapi-deprecation[redis]"
```
*(Requires `redis>=5.0.0`)*

**Usage:**
```python
from redis.asyncio import Redis
from fastapi_deprecation.metrics import DeprecationTracker
from fastapi_deprecation.metrics.redis import RedisMetricsStore

redis_client = Redis.from_url("redis://localhost:6379")
tracker = DeprecationTracker(store=RedisMetricsStore(redis_client))

# Binds exactly the same way
set_deprecation_callback(tracker.record_usage)
```

### Prometheus Scraper

The Prometheus backend directly exposes multi-dimensional data in standard Prometheus exposition text format using the official Python client. It intelligently encodes schedule metadata (`sunset_date`, `deprecation_date`) into auxiliary `Info` metrics alongside standard `Counter` dimensions.

**Installation:**
```bash
pip install "fastapi-deprecation[prometheus]"
```
*(Requires `prometheus-client>=0.20.0`)*

**Usage:**
```python
from fastapi import Response
from fastapi_deprecation.metrics import DeprecationTracker
from fastapi_deprecation.metrics.prometheus import PrometheusMetricsStore

tracker = DeprecationTracker(store=PrometheusMetricsStore())
set_deprecation_callback(tracker.record_usage)

@app.get("/metrics/deprecation")
async def get_prometheus_metrics():
    # Returns raw text string formatting required by prometheus scraper
    exposition_text = await tracker.export_text()
    return Response(content=exposition_text, media_type="text/plain")
```

> **Warning:** Do **not** use `await tracker.export_json()` with the `PrometheusMetricsStore`. Prometheus scrapers strictly expect metrics formatted as plain-text exposition. Calling `export_json()` with the Prometheus backend will raise a `NotImplementedError`.
