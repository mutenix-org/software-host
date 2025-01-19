# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import json
import logging
from typing import Callable

from aiohttp import web
from mutenix.hid_commands import HidOutputMessage
from mutenix.hid_commands import SetLed
from mutenix.hid_commands import Status
from mutenix.web_server import WebServer

HOST = "127.0.0.1"
PORT = 12909

_logger = logging.getLogger(__name__)


class UnsupportedMessageTypeError(Exception):
    """Exception raised for unsupported message types in VirtualMacropad."""

    pass


class VirtualMacropad(WebServer):
    """A virtual representation of the Macropad for testing or playing around."""

    def __init__(self, host: str = HOST, port: int = PORT):
        super().__init__(host, port)
        self._callbacks: list[Callable[[HidOutputMessage], asyncio.Future]] = []
        self._websockets: set[web.WebSocketResponse] = set()
        self._led_status: dict[int, str] = {}
        self._led_input_status: dict[int, str] = {}
        self._led_status_lock = asyncio.Lock()

        self.app.add_routes(
            [
                web.post("/button", self.button_handler),
                web.get("/ws", self.websocket_handler),
                web.post("/led", self.led_handler),
            ],
        )

    def register_callback(self, callback: Callable[[HidOutputMessage], asyncio.Future]):
        self._callbacks.append(callback)

    async def button_handler(self, request: web.Request):
        data = await request.json()
        await self._handle_msg(Status.trigger_button(data.get("button")))
        return web.Response(status=200)

    async def _handle_msg(self, msg: HidOutputMessage):
        for callback in self._callbacks:
            await callback(msg)

    async def handle_state_request(self, ws):
        async with self._led_status_lock:
            for i, color in self._led_status.items():
                if color:
                    await ws.send_json({"button": i, "color": color})

    async def websocket_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._websockets.add(ws)
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                match data["command"]:
                    case "button":
                        await self._handle_msg(
                            Status.trigger_button(data.get("button")),
                        )
                    case "state_request":
                        await self.handle_state_request(ws)
                    case _:
                        _logger.info("Unknown message: %s", data)
                        await ws.send_json({"error": "unknown command"})
            else:
                _logger.info("Unknown message: %s", msg)
                await ws.send_json({"error": "unknown message"})
        self._websockets.remove(ws)
        return ws

    @staticmethod
    async def _send_json_safe(ws, data):
        try:
            await ws.send_json(data)
        except Exception as e:
            _logger.error("Error sending LED status: %s to websocket %s", e, ws)

    def _send_led_status(self, button: int, color: str):
        for ws in self._websockets:
            asyncio.create_task(
                self._send_json_safe(ws, {"button": button, "color": color}),
            )

    async def send_msg(self, msg: HidOutputMessage):
        if isinstance(msg, SetLed):
            color = msg.color.name.lower()
            async with self._led_status_lock:
                self._led_status[msg.id] = color
            self._send_led_status(msg.id, color)
        else:
            raise UnsupportedMessageTypeError("Unsupported message type")
        _logger.debug("Sent message: %s", msg)

    async def led_handler(self, request: web.Request):
        data = await request.json()
        self._led_input_status[int(data["button"])] = data["color"]
        return web.Response(status=200)

    def get_led_status(self, button: int) -> str:
        return self._led_input_status.get(button, "black")
