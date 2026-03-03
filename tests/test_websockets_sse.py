from datetime import timedelta
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from starlette import status
from starlette.responses import StreamingResponse

from fastapi_deprecation import (
    DeprecationMiddleware,
    deprecated,
)
from datetime import datetime, timezone


def test_websocket_decorator_warn():
    app = FastAPI()

    @app.websocket("/ws")
    @deprecated(deprecation_date=datetime.now(timezone.utc) - timedelta(days=1))
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Hello WebSockets")
        await websocket.close()

    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_text()
        assert data == "Hello WebSockets"

        # TestClient currently doesn't expose the underlying response headers from the upgrade request
        # natively on the WebSocket object in a trivial way, but we can verify it doesn't crash
        # and correctly accepts the connection.


def test_websocket_decorator_block():
    app = FastAPI()

    @app.websocket("/ws")
    @deprecated(sunset_date=datetime.now(timezone.utc) - timedelta(days=1))
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()

    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            pass

    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION


def test_websocket_middleware_block():
    app = FastAPI()

    @app.websocket("/ws/test")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()

    from fastapi_deprecation.engine import DeprecationConfig

    app.add_middleware(
        DeprecationMiddleware,
        deprecations={
            "/ws": DeprecationConfig(
                sunset_date=datetime.now(timezone.utc) - timedelta(days=1)
            )
        },
    )

    client = TestClient(app)

    # In middleware blocking, we return a 410 HTTP response to the websocket upgrade.
    # To test this gracefully without wrestling TestClient's internal Exception mapping, we can just issue a GET Request
    # to the upgrade endpoint, as WebSocket handshakes start as GETs.
    response = client.get(
        "/ws/test", headers={"Connection": "Upgrade", "Upgrade": "websocket"}
    )
    assert response.status_code == 410
    assert "deprecated" in response.text


def test_sse_sunset():
    app = FastAPI()

    async def event_stream() -> AsyncGenerator[str, None]:
        yield "event: message\ndata: 1\n\n"
        yield "event: message\ndata: 2\n\n"

    @app.get("/stream")
    # We use a custom response here because normally a sunset block just returns a 410.
    # To test the SSE stream interceptor directly, we need to bypass the standard 410 block
    # to actually execute the stream.
    @deprecated(
        sunset_date=datetime.now(timezone.utc) - timedelta(days=1),
        response=lambda: StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
        ),
    )
    async def stream():
        # This function body acts as a dummy since the decorator response overrides it
        pass

    client = TestClient(app)

    # Sunset is in the past, generator should immediately yield sunset and stop
    response = client.get("/stream")
    assert response.status_code == 200

    content = response.text
    assert "event: sunset" in content
    assert "Endpoint has been sunset and connection closed." in content
    assert "event: message\ndata: 1" not in content


def test_sse_warn():
    app = FastAPI()

    async def event_stream() -> AsyncGenerator[str, None]:
        yield "event: message\ndata: 1\n\n"
        yield "event: message\ndata: 2\n\n"

    @app.get("/stream")
    @deprecated(
        deprecation_date=datetime.now(timezone.utc) - timedelta(days=1),
    )
    async def stream():
        # During the WARN phase, the function itself is executed
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
        )

    client = TestClient(app)

    # Sunset is NOT set, we should get standard Warning headers and original SSE data!
    response = client.get("/stream")
    assert response.status_code == 200

    assert "Deprecation" in response.headers
    content = response.text
    assert "event: message\ndata: 1" in content
    assert "event: sunset" not in content


def test_sse_brownout():
    app = FastAPI()

    async def event_stream() -> AsyncGenerator[str, None]:
        yield "event: message\ndata: 1\n\n"
        yield "event: message\ndata: 2\n\n"

    # Probability set to 1.0 (100% chance to fail) guarantees the stream will hit a brownout immediately

    @app.get("/stream")
    @deprecated(
        brownout_probability=1.0,
        response=lambda: StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
        ),
    )
    async def stream():
        pass

    client = TestClient(app)

    # Sunset is NOT explicitly reached, but the 100% brownout probability should kill the generator.
    response = client.get("/stream")
    assert response.status_code == 200

    content = response.text
    assert "event: sunset" in content
    assert "Endpoint has been sunset and connection closed." in content
    assert "event: message\ndata: 1" not in content
