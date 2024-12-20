import asyncio
import websockets
import logging
from mutenix.teams_messages import ServerMessage, ClientMessage
from typing import Callable

_logger = logging.getLogger(__name__)


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

    async def _connect(self):
        if not self._run:
            _logger.debug("Not running, skip connecting")
            return
        if self._connecting:
            _logger.debug("Other connection in progress, wait for completion")
            while self._connecting:
                await asyncio.sleep(0.1)
            return
        self._connecting = True
        while self._run:
            connection = await self._do_connect()
            if not connection:
                await asyncio.sleep(0.25)
            else:
                self._connection = connection
                break
        self._connecting = False

    async def _do_connect(self):
        try:
            connection = await websockets.connect(self._uri)
            _logger.info(f"Connected to WebSocket server at {self._uri}")
            return connection
        except Exception as e:
            _logger.info(f"Failed to connect to WebSocket server: {type(e).__name__}: {e}")
            return None

    def send_message(self, message: ClientMessage):
        future = asyncio.get_event_loop().create_future()
        self._send_queue.put_nowait((message, future))
        return future

    def register_callback(self, callback: Callable[[ServerMessage], None]):
        self._callback = callback

    async def _send_loop(self):
        while self._run:
            await self._send()
        _logger.info("Send loop stopped")

    async def _send(self):
        try:
            queue_element = self._send_queue.get_nowait()
            message, future = queue_element
        except asyncio.QueueEmpty:
            _logger.debug("Send queue empty")
            await asyncio.sleep(0.01)
            return
        try:
            if isinstance(message, ClientMessage):
                msg = message.model_dump_json(by_alias=True)
            else:
                future.set_exception(TypeError("Expected message to be an instance of ClientMessage"))
                return
            await self._connection.send(msg)
            future.set_result(True)
        except Exception as e:
            future.set_exception(e)
            await self._connect()
        finally:
            self._send_queue.task_done()

    async def _receive_loop(self):
        while self._run:
            await self._receive()
        _logger.info("Receive loop stopped")

    async def _receive(self):
        try:
            async with asyncio.timeout(0.01):
                _logger.debug("Checking receive")
                msg = await self._connection.recv()
                _logger.debug(f"Received message: {msg}")
                message = ServerMessage.model_validate_json(msg)
                if message:
                    _logger.debug(f"Decoded message: {message}")
                if self._callback:
                    if asyncio.iscoroutinefunction(self._callback):
                        asyncio.create_task(self._callback(message))
                    else:
                        self._callback(message)
        except asyncio.TimeoutError:
            _logger.debug("Receive timed out stopped")
            await asyncio.sleep(0.01)
            pass
        except Exception as e:
            _logger.error(f"Error receiving message: {e}")
            await self._connect()

    async def process(self):
        while self._run:
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
