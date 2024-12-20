import asyncio
import json
from aiohttp import web
from mutenix.hid_commands import Status, HidOutputMessage, SetLed
import logging

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
        self._websockets = set()
        self._led_status = {}
        self._led_status_lock = asyncio.Lock()

    def register_callback(self, callback):
        self._callback = callback

    async def index(self, request):
        return web.Response(
            text="""
            <html>
            <body>
            <div id="mainDiv" style="background-color: black; border-radius: 10px; padding: 20px; display: flex; flex-direction: column; align-items: center; width: 150px;">
            <div style="display: flex; align-items: center;">
                <button style="background-color: green; border-radius: 50%; margin: 5px; padding: 30px;" title="(Un)Mute" onclick="sendButtonPress(1)"></button>
                <div id="indicator1" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            <div style="display: flex; align-items: center;">
                <button style="background-color: yellow; border-radius: 50%; margin: 5px; padding: 30px;" title="Lower/Raise Hand" onclick="sendButtonPress(2)"></button>
                <div id="indicator2" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            <div style="display: flex; align-items: center;">
                <button style="background-color: black; color:white; border-radius: 50%; margin: 5px; padding: 30px;" title="Show Teams" onclick="sendButtonPress(3)"></button>
                <div id="indicator3" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            <div style="display: flex; align-items: center;">
                <button style="background-color: blue; border-radius: 50%; margin: 5px; padding: 30px;" title="Like" onclick="sendButtonPress(4)"></button>
                <div id="indicator4" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            <div style="display: flex; align-items: center;">
                <button style="background-color: red; border-radius: 50%; margin: 5px; padding: 30px;" title="Leave Call" onclick="sendButtonPress(5)"></button>
                <div id="indicator5" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            </div>
            <button onclick="openPopup()">Open in Popup</button>
            <script>
            function openPopup() {
                const mainDiv = document.getElementById('mainDiv');
                const width = mainDiv.offsetWidth;
                const height = mainDiv.offsetHeight;
                const popup = window.open('', 'popup', `width=${width+20},height=${height+20},toolbar=no,location=no,status=no,menubar=no,scrollbars=yes,resizable=yes`);
                popup.document.write(document.documentElement.outerHTML);
                popup.document.close();
                popup.focus();
            }
            </script>
            <script>
            const ws = new WebSocket('ws://' + window.location.host + '/ws');
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                document.getElementById('indicator' + data.button).style.backgroundColor = data.color;
            };
            async function sendButtonPress(button) {
                ws.send(JSON.stringify({button: button}));
            }
            ws.onopen = function() {
                ws.send(JSON.stringify({state_request: true}));
            };
            ws.onclose = function() {
                console.log('WebSocket connection closed');
            };
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                document.getElementById('indicator' + data.button).style.backgroundColor = data.color;
            };
            async function sendButtonPress(button) {
                ws.send(JSON.stringify({button: button}));
            }
            window.onblur = function() {
                ws.send(JSON.stringify({state_request: true}));
            };
            window.onfocus = function() {
                ws.send(JSON.stringify({state_request: true}));
            };
            </script>
            </body>
            </html>
        """,
            content_type="text/html",
        )

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
