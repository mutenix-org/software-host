import asyncio
import json
from aiohttp import web
from mutenix.hid_commands import Status, HidOutputMessage, SetLed
import logging
from aiohttp_jinja2 import setup as jinja2_setup, render_template
import jinja2

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080

_logger = logging.getLogger(__name__)

class UnsupportedMessageTypeError(Exception):
    """Exception raised for unsupported message types in VirtualMacropad."""
    pass

class VirtualMacropad:
    """A virtual representation of the Macropad for testing or playing around."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        # Callback function to handle button press events
        self._callback = None
        self.app = web.Application()
        self.app.add_routes(
            [
                web.get("/", self.index),
                web.post("/button", self.button_handler),
                web.get("/ws", self.websocket_handler),
            ]
        )
        jinja2_setup(self.app, loader=jinja2.FileSystemLoader('/path/to/templates'))
        self._websockets = set()
        self._led_status = {}
        self._led_status_lock = asyncio.Lock()

    def register_callback(self, callback):
        self._callback = callback

    async def index(self, request):
        return render_template('index.html', request, {})

    async def button_handler(self, request):
        data = await request.json()
        button = data.get("button")
        if self._callback:
            msg = Status.trigger_button(button)
            await self._callback(msg)
        return web.Response(status=200)

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._websockets.add(ws)
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "button" in data:
                    button = data.get("button")
                    if self._callback:
                        msg = Status.trigger_button(button)
                        await self._callback(msg)
                if "state_request" in data:
                    async with self._led_status_lock:
                        for i, color in self._led_status.items():
                            if color:
                                await ws.send_json({"button": i, "color": color})
        self._websockets.remove(ws)
        return ws

    def _send_led_status(self, button, color):
        async def send_json_safe(ws, data):
            try:
                await ws.send_json(data)
            except Exception as e:
                _logger.error(f"Error sending LED status: {e} to websocket {ws}")

        for ws in self._websockets:
            asyncio.create_task(send_json_safe(ws, {"button": button, "color": color}))

    async def send_msg(self, msg: HidOutputMessage):
        if isinstance(msg, SetLed):
            color = msg.color.name.lower()
            async with self._led_status_lock:
                self._led_status[msg.id] = color
            self._send_led_status(msg.id, color)
        else:
            raise UnsupportedMessageTypeError("Unsupported message type")
        _logger.debug(f"Sent message: {msg}")

    async def process(self):
        runner = web.AppRunner(self.app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        _logger.info(f"VirtualMacropad running at http://{self.host}:{self.port}")
        print(f"VirtualMacropad running at http://{self.host}:{self.port}")

    async def stop(self):
        await self.app.shutdown()
        await self.app.cleanup()
        _logger.info("VirtualMacropad stopped")
