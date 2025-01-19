# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import logging
from typing import Callable

import websockets
from mutenix.teams_messages import ClientMessage
from mutenix.teams_messages import ServerMessage
from mutenix.utils import block_parallel
from mutenix.utils import rate_limited_logger
from mutenix.utils import run_loop

_logger = logging.getLogger(__name__)


@rate_limited_logger(_logger, limit=3, interval=10)
def _log_failed_to_connect(*args, **kwargs):
    _logger.error(*args, **kwargs)


class Identifier:
    """Identifies the device to the Teams Websocket server.
    The token is used to authenticate the device with the server. It is received once the user
    allows the device to connect to Teams."""

    def __init__(self, manufacturer, device, app, app_version, token=""):
        self.protocol_version = "2.0.0"
        self.manufacturer = manufacturer
        self.device = device
        self.app = app
        self.app_version = app_version
        self.token = token


class WebSocketClient:
    """Handles the WebSocket connection to Teams."""

    RETRY_INTERVAL = 0.25

    def __init__(self, uri: str, identifier: Identifier):
        self._uri = uri
        self._connection = None
        self._send_queue: asyncio.Queue[tuple[ClientMessage, asyncio.Future]] = (
            asyncio.Queue()
        )
        self._callback: Callable[[ServerMessage], None] | None = None
        params = (
            f"?protocol-version={identifier.protocol_version}"
            f"&manufacturer={identifier.manufacturer}"
            f"&device={identifier.device}"
            f"&app={identifier.app}"
            f"&app-version={identifier.app_version}"
            f"&token={identifier.token}"
        )
        self._uri += params
        self._connecting = False
        self._run = True
        self._sent_something = True

    @block_parallel
    async def _connect(self):
        while self._run:
            self._connection = None
            connection = await self._do_connect()
            if not connection:
                await asyncio.sleep(self.RETRY_INTERVAL)
            else:
                self._connection = connection
                break

    async def _do_connect(self):
        try:
            connection = await websockets.connect(self._uri)
            _logger.info("Connected to WebSocket server at %s", self._uri)
            return connection
        except Exception as e:
            _log_failed_to_connect(
                "Failed to connect to WebSocket server: %s: %s",
                type(e).__name__,
                e,
            )
            return None

    def send_message(self, message: ClientMessage):
        future = asyncio.get_event_loop().create_future()
        self._send_queue.put_nowait((message, future))
        return future

    def register_callback(self, callback: Callable[[ServerMessage], None]):
        self._callback = callback

    async def _send(self):
        try:
            queue_element = self._send_queue.get_nowait()
            message, future = queue_element
        except asyncio.QueueEmpty:
            if self._sent_something:
                self._sent_something = False
                _logger.debug("Send queue empty")
            await asyncio.sleep(0.2)
            return
        try:
            if isinstance(message, ClientMessage):
                msg = message.model_dump_json(by_alias=True)
                self._sent_something = True
            else:
                future.set_exception(
                    TypeError("Expected message to be an instance of ClientMessage"),
                )
                return
            await self._connection.send(msg)
            if not future.done():
                future.set_result(True)
        except Exception as e:
            future.set_exception(e)
            await self._connect()
        finally:
            self._send_queue.task_done()

    async def _receive(self):
        try:
            async with asyncio.timeout(1):
                msg = await self._connection.recv()
                _logger.debug("Received message: %s", msg)
                message = ServerMessage.model_validate_json(msg)
                if message:
                    _logger.debug("Decoded message: %s", message)
                if self._callback:
                    if asyncio.iscoroutinefunction(self._callback):
                        asyncio.create_task(self._callback(message))
                    else:
                        self._callback(message)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            _logger.error("Error receiving message: %s", e)
            await self._connect()

    async def process(self):
        while self._run:
            asyncio.current_task().set_name("WebSocketClient.process")
            try:
                await self._connect()
                await asyncio.gather(self._send_loop(), self._receive_loop())
            except asyncio.CancelledError as e:
                _logger.info("shutting down due to cancel: %s", e)
                await self.stop()

    async def stop(self):
        self._run = False
        if self._connection:
            await self._connection.close()
        while not self._send_queue.empty():
            _, future = self._send_queue.get_nowait()
            future.set_exception(RuntimeError("WebSocketClient is stopping"))
            self._send_queue.task_done()

    @property
    def connected(self) -> bool:  # pragma: no cover
        return self._connection is not None

    _receive_loop = run_loop(_receive)
    _send_loop = run_loop(_send)
