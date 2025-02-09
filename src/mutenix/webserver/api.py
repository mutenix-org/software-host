import asyncio
import logging
from typing import Callable

from aiohttp import web
from mutenix.models.config import LedColor
from mutenix.models.hid_commands import HidOutputMessage
from mutenix.models.hid_commands import Status
from mutenix.models.state import State
from mutenix.webserver.model import ButtonRequest
from mutenix.webserver.model import LedRequest
from pydantic import ValidationError


_logger = logging.getLogger(__name__)


class APIHandler:
    def __init__(self, state: State):
        self._callbacks: list[Callable[[HidOutputMessage], asyncio.Future]] = []
        self._state = state
        self._led_status: dict[int, str] = {}
        self._led_input_status: dict[int, str] = {}
        self._led_status_lock = asyncio.Lock()

    async def handle_hardware_info(self, request: web.Request):
        return web.json_response(
            {
                "hardware": self._state.hardware.variant,
                "version": self._state.hardware.version,
            },
        )

    async def handle_button(self, request: web.Request):
        try:
            data = ButtonRequest.model_validate_json(await request.text())
        except ValidationError as e:
            _logger.error(f"Invalid button request: {e}")
            return web.Response(status=400)
        await self._handle_msg(Status.trigger_button(data.button))
        return web.Response(status=200)

    async def _handle_msg(self, msg: HidOutputMessage):
        for callback in self._callbacks:
            await callback(msg)

    def register_callback(self, callback):
        self._callbacks.append(callback)

    async def handle_post_led(self, request: web.Request):
        try:
            data = LedRequest.model_validate_json(await request.text())
        except ValidationError as e:
            _logger.error(f"Invalid Led request: {e}")
            return web.Response(status=400)
        if data.color not in LedColor:
            _logger.error(f"Invalid color: {data.color}")
            return web.Response(status=400)
        if data.button > 10 or data.button < 1:
            return web.Response(status=404)
        self._led_input_status[data.button] = data.color
        return web.Response(status=200)

    async def handle_get_led(self, request: web.Request):
        try:
            button = int(request.query.get("button", 0))
        except Exception as e:
            _logger.error(f"Invalid button: {e}")
            return web.Response(status=400)
        if button > 10:
            return web.Response(status=404)
        color = self._led_input_status.get(button, "black")
        return web.json_response({"button": button, "color": color})

    def setup_routes(self, app: web.Application, prefix: str = "/api"):
        app.router.add_route(
            "GET",
            f"{prefix}/hardware_info",
            self.handle_hardware_info,
        )
        app.router.add_route("POST", f"{prefix}/button", self.handle_button)
        app.router.add_route("GET", f"{prefix}/led", self.handle_get_led)
        app.router.add_route("POST", f"{prefix}/led", self.handle_post_led)
