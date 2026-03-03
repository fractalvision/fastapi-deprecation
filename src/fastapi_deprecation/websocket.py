from typing import Any, Mapping, Optional

from fastapi import WebSocket
from fastapi.exceptions import WebSocketException
from starlette import status

from .engine import DeprecationResult, apply_headers


class DeprecatedWebSocket:
    """
    A wrapper around a standard FastAPI WebSocket that automatically injects
    deprecation headers when `accept()` is called.
    """

    def __init__(self, websocket: WebSocket, result: DeprecationResult):
        self._websocket = websocket
        self._result = result

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
