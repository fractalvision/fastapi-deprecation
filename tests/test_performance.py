from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
from starlette.responses import StreamingResponse

from fastapi_deprecation import (
    deprecated,
    DeprecationMiddleware,
    deprecated_sse_generator,
)
from fastapi_deprecation.engine import DeprecationConfig

# --- Vanilla Setup ---
app_vanilla = FastAPI()


@app_vanilla.get("/endpoint")
async def vanilla_endpoint():
    return {"status": "ok"}


client_vanilla = TestClient(app_vanilla)

# --- Decorator Setup ---
app_decorator = FastAPI()


@app_decorator.get("/endpoint")
@deprecated(sunset_date=datetime.now(timezone.utc) + timedelta(days=1))
async def decorated_endpoint():
    return {"status": "ok"}


client_decorator = TestClient(app_decorator)

# --- Middleware Setup ---
app_middleware = FastAPI()
app_middleware.add_middleware(
    DeprecationMiddleware,
    deprecations={
        "/endpoint": DeprecationConfig(
            sunset_date=datetime.now(timezone.utc) + timedelta(days=1)
        )
    },
)


@app_middleware.get("/endpoint")
async def middleware_endpoint():
    return {"status": "ok"}


client_middleware = TestClient(app_middleware)


# --- SSE Vanilla Setup ---
async def simple_event_stream() -> AsyncGenerator[str, None]:
    yield "event: message\ndata: 1\n\n"


app_sse_vanilla = FastAPI()


@app_sse_vanilla.get("/stream")
async def sse_vanilla_endpoint():
    return StreamingResponse(simple_event_stream(), media_type="text/event-stream")


client_sse_vanilla = TestClient(app_sse_vanilla)

# --- SSE Wrapped Setup ---
app_sse_wrapped = FastAPI()
config = DeprecationConfig(sunset_date=datetime.now(timezone.utc) + timedelta(days=1))


@app_sse_wrapped.get("/stream")
async def sse_wrapped_endpoint():
    return StreamingResponse(
        deprecated_sse_generator(simple_event_stream(), config),
        media_type="text/event-stream",
    )


client_sse_wrapped = TestClient(app_sse_wrapped)


# --- Benchmarks ---


def test_benchmark_vanilla_http(benchmark):
    benchmark(client_vanilla.get, "/endpoint")


def test_benchmark_decorator_http(benchmark):
    benchmark(client_decorator.get, "/endpoint")


def test_benchmark_middleware_http(benchmark):
    benchmark(client_middleware.get, "/endpoint")


def test_benchmark_vanilla_sse(benchmark):
    benchmark(client_sse_vanilla.get, "/stream")


def test_benchmark_wrapped_sse(benchmark):
    benchmark(client_sse_wrapped.get, "/stream")
