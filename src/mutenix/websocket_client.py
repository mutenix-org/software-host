import asyncio
import websockets
import logging
from pydantic import ValidationError
from mutenix.teams_messages import ServerMessage, ClientMessage

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

    def __init__(self, uri: str, identifier):
        self._uri = uri
        self._connection = None
        self._send_queue = asyncio.Queue()
        self._callback = None
        params = f"?protocol-version={identifier.protocol_version}&manufacturer={identifier.manufacturer}&device={identifier.device}&app={identifier.app}&app-version={identifier.app_version}&token={identifier.token}"
        self._uri += params
        self._connecting = False

    async def _connect(self):
        if self._connecting:
            _logger.debug("Other connection in progress, wait for completion")
            while self._connecting:
                await asyncio.sleep(0.1)
            return
        self._connecting = True
        while True:
            try:
                self.connection = await websockets.connect(self._uri)
                _logger.info(f"Connected to WebSocket server at {self._uri}")
                break
            except Exception as e:
                _logger.info(f"Failed to connect to WebSocket server: {e}")
                await asyncio.sleep(1)
        self._connecting = False

    def send_message(self, message: ClientMessage):
        future = asyncio.get_event_loop().create_future()
        self._send_queue.put_nowait((message, future))
        return future

    def register_callback(self, callback: callable):
        self._callback = callback

    async def _send_loop(self):
        while True:
            message, future = await self._send_queue.get()
            try:
                msg = message.model_dump_json(by_alias=True)
                await self.connection.send(msg)
                future.set_result(True)
            except ValidationError as e:
                _logger.error("Unpackable message: %s", message)
                _logger.error("Error: %s", e)
                future.set_exception(e)
            except Exception as e:
                future.set_exception(e)
                await self._connect()
            finally:
                self._send_queue.task_done()

    async def _receive_loop(self):
        while True:
            try:
                message = await self.connection.recv()
                message = ServerMessage.model_validate_json(message)
                if self._callback:
                    if asyncio.iscoroutinefunction(self._callback):
                        asyncio.create_task(self._callback(message))
                    else:
                        self._callback(message)
            except Exception as e:
                _logger.error(f"Error receiving message: {e}")
                await self._connect()

    async def process(self):
        while True:
            try:
                await self._connect()
                await asyncio.gather(self._send_loop(), self._receive_loop())
            except Exception as e:
                _logger.info("Error processing WebSocket connection: %s", e)
