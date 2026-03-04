import pytest
from fastapi import Response

from fastapi_deprecation.engine import DeprecationConfig
from fastapi_deprecation.metrics import DeprecationTracker
from fastapi_deprecation.metrics.prometheus import PrometheusMetricsStore


@pytest.fixture
def prometheus_tracker():
    try:
        import prometheus_client  # noqa: F401
    except ImportError:
        pytest.skip("prometheus_client is not installed")

    # Clear out registry to prevent test pollution
    from prometheus_client import REGISTRY

    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        REGISTRY.unregister(collector)

    store = PrometheusMetricsStore()
    return DeprecationTracker(store)


@pytest.mark.asyncio
async def test_prometheus_exposition_format(prometheus_tracker: DeprecationTracker):
    req_warn = {"method": "POST", "path": "/v1/upload", "type": "http"}
    res_warn = Response(status_code=200)

    req_block = {"method": "POST", "path": "/v1/upload", "type": "http"}
    res_block = Response(status_code=410)

    from datetime import datetime, timezone

    config = DeprecationConfig(sunset_date=datetime.now(timezone.utc))

    # Hit warnings
    await prometheus_tracker.record_usage(req_warn, res_warn, config)
    await prometheus_tracker.record_usage(req_warn, res_warn, config)

    # Hit block
    await prometheus_tracker.record_usage(req_block, res_block, config)

    # Export metrics as Prometheus text format
    exported_text = await prometheus_tracker.export_text()

    assert "fastapi_deprecation_requests_total" in exported_text

    # The exposition format should contain something like:
    # fastapi_deprecation_requests_total{method="POST",path="/v1/upload",phase="warn"} 2.0
    # fastapi_deprecation_requests_total{method="POST",path="/v1/upload",phase="block"} 1.0

    assert 'phase="warn"' in exported_text
    assert 'phase="block"' in exported_text
    assert 'method="POST"' in exported_text
    assert 'path="/v1/upload"' in exported_text

    # Metadata should be exposed via Info
    assert "fastapi_deprecation_endpoint_info" in exported_text
    assert 'sunset_date="' in exported_text
