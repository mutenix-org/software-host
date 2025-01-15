# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import json
import logging
import pathlib
from typing import Callable

import jinja2
import markdown
from aiohttp import web
from aiohttp_jinja2 import render_template
from aiohttp_jinja2 import setup as jinja2_setup
from mutenix.hid_commands import HidOutputMessage
from mutenix.hid_commands import SetLed
from mutenix.hid_commands import Status

HOST = "127.0.0.1"
PORT = 12909

_logger = logging.getLogger(__name__)


class UnsupportedMessageTypeError(Exception):
    """Exception raised for unsupported message types in VirtualMacropad."""

    pass


class VirtualMacropad:
    """A virtual representation of the Macropad for testing or playing around."""

    icons: list[dict[str, str]] = [
        {
            "src": "/favicon/32",
            "sizes": "32x32",
            "type": "image/png",
        },
        {
            "src": "/favicon/16",
            "sizes": "16x16",
            "type": "image/png",
        },
        {
            "src": "/favicon/apple_touch",
            "sizes": "180x180",
            "type": "image/png",
        },
    ]

    def __init__(self, host: str = HOST, port: int = PORT):
        self.host = host
        self.port = port
        self._callbacks: list[Callable[[HidOutputMessage], asyncio.Future]] = []
        self.app = web.Application()
        self.app.router.add_static(
            "/static/",
            path=str(pathlib.Path(__file__).parent / "static"),
            name="static",
        )
        self.app.router.add_route("GET", "/favicon/{filename}", self.favicon)
        self.app.router.add_route("GET", "/favicon.svg", self.favicon_svg)
        self.app.router.add_route("GET", "/site.webmanifest", self.serve_manifest)
        self.app.router.add_route("GET", "/help", self.help)
        self.app.router.add_route("GET", "/about", self.about)
        self.app.add_routes(
            [
                web.get("/", self.index),
                web.post("/button", self.button_handler),
                web.get("/ws", self.websocket_handler),
            ],
        )
        jinja2_setup(self.app, loader=jinja2.PackageLoader("mutenix", "templates"))
        self._websockets: set[web.WebSocketResponse] = set()
        self._led_status: dict[int, str] = {}
        self._led_status_lock = asyncio.Lock()

    def register_callback(self, callback: Callable[[HidOutputMessage], asyncio.Future]):
        self._callbacks.append(callback)

    async def index(self, request: web.Request):
        return render_template("index.html", request, {})

    async def button_handler(self, request: web.Request):
        data = await request.json()
        await self._handle_msg(Status.trigger_button(data.get("button")))
        return web.Response(status=200)

    async def favicon(self, request: web.Request):
        filename = request.match_info["filename"]
        for icon in self.icons:
            if icon["src"].endswith(filename):
                icon_path = (
                    pathlib.Path(__file__).parent
                    / "assets"
                    / f"icon_active_{filename}.png"
                )
                break
        else:
            raise web.HTTPNotFound()
        return web.FileResponse(icon_path)

    async def favicon_svg(self, request: web.Request):
        return web.FileResponse(
            pathlib.Path(__file__).parent
            / "assets"
            / "mutenix_logo_finalicon_active.svg",
        )

    async def serve_manifest(self, request: web.Request):
        manifest = {
            "name": "Mutenix Virtual Macropad",
            "short_name": "Mutenix",
            "icons": self.icons,
            "start_url": "/",
            "display": "standalone",
        }
        return web.json_response(manifest)

    async def help(self, request: web.Request):
        return render_template("help.html", request, {})

    async def about(self, request: web.Request):
        readme_path = pathlib.Path(__file__).parent.parent.parent / "README.md"
        license_path = pathlib.Path(__file__).parent.parent.parent / "LICENSE"
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
        with open(license_path, "r", encoding="utf-8") as f:
            license_content = f.read()
        html_readme_content = markdown.markdown(readme_content)
        html_license_content = markdown.markdown(license_content)
        context = {
            "readme_content": html_readme_content,
            "license_content": html_license_content,
        }
        return render_template("about.html", request, context)

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

    async def process(self):
        runner = web.AppRunner(self.app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        _logger.info("VirtualMacropad running at http://%s:%s", self.host, self.port)

    async def stop(self):
        await self.app.shutdown()
        await self.app.cleanup()
        _logger.info("VirtualMacropad stopped")
