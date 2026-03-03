import time
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from fastapi import WebSocket
from fastapi.exceptions import WebSocketException
from starlette import status

from .engine import (
    DeprecationConfig,
    DeprecationResult,
    ActionType,
    apply_headers,
    process_deprecation,
)


class DeprecatedWebSocket:
    """
    A wrapper around a standard FastAPI WebSocket that automatically injects
    deprecation headers when `accept()` is called.
    """

    def __init__(
        self, websocket: WebSocket, result: DeprecationResult, config: DeprecationConfig
    ):
        self._websocket = websocket
        self._result = result
        self._config = config
        self._last_check_time = 0.0

    def _check_deprecation(self):
        """Evaluate deprecation status mid-stream, throttled to 1 second."""
        current_time = time.monotonic()
        if current_time - self._last_check_time >= 1.0:
            now = datetime.now(timezone.utc)
            result = process_deprecation(self._config, now)
            self._last_check_time = current_time
            if result.action == ActionType.BLOCK:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason=self._config.detail or "Endpoint Sunset",
                )

    def __getattr__(self, name: str) -> Any:
        # Proxy all attributes to the underlying websocket
        return getattr(self._websocket, name)

    async def accept(
        self,
        subprotocol: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        """
        Accept the websocket connection, injecting deprecation headers.
        """
        # We need to construct a new headers dict that includes the deprecation headers
        new_headers = dict(headers) if headers else {}

        apply_headers(new_headers, self._result.headers)

        await self._websocket.accept(subprotocol=subprotocol, headers=new_headers)

    async def handle_block(self, config: Any) -> None:
        """
        Handle a blocking situation. We send a close frame if the connection
        hasn't been accepted yet, or raise an exception.
        """
        # FastAPI typically expects a WebSocketException if we are rejecting a route
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=config.detail or "Endpoint Sunset",
        )

    async def receive_text(self, *args, **kwargs) -> str:
        self._check_deprecation()
        return await self._websocket.receive_text(*args, **kwargs)

    async def receive_bytes(self, *args, **kwargs) -> bytes:
        self._check_deprecation()
        return await self._websocket.receive_bytes(*args, **kwargs)

    async def receive_json(self, *args, **kwargs) -> Any:
        self._check_deprecation()
        return await self._websocket.receive_json(*args, **kwargs)

    async def receive(self, *args, **kwargs) -> dict:
        self._check_deprecation()
        return await self._websocket.receive(*args, **kwargs)

    async def send_text(self, *args, **kwargs) -> None:
        self._check_deprecation()
        await self._websocket.send_text(*args, **kwargs)

    async def send_bytes(self, *args, **kwargs) -> None:
        self._check_deprecation()
        await self._websocket.send_bytes(*args, **kwargs)

    async def send_json(self, *args, **kwargs) -> None:
        self._check_deprecation()
        await self._websocket.send_json(*args, **kwargs)

    async def send(self, *args, **kwargs) -> None:
        self._check_deprecation()
        await self._websocket.send(*args, **kwargs)
