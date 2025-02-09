import logging

import jinja2
from aiohttp import web
from aiohttp_jinja2 import setup as jinja2_setup
from mutenix.models.config import VirtualMacropadConfig
from mutenix.models.hid_commands import HidOutputMessage
from mutenix.models.state import State
from mutenix.webserver.api import APIHandler
from mutenix.webserver.browser import BrowserHandler
from mutenix.webserver.pages import PageHandler
from mutenix.webserver.static import StaticHandler
from mutenix.webserver.virtual_macropad import VirtualMacropadHandler
from mutenix.webserver.websocket import WebSocketHandler

_logger = logging.getLogger(__name__)


class WebServer:
    def __init__(self, state: State, config: VirtualMacropadConfig):
        self._host = config.bind_address
        self._port = config.bind_port
        self._state = state
        self._running = False
        self.app = web.Application()
        jinja2_setup(self.app, loader=jinja2.PackageLoader("mutenix", "templates"))
        self._setup_handlers()
        self._setup_routes()

    def _setup_handlers(self):
        self.static_handler = StaticHandler()
        self.page_handler = PageHandler(self._state)
        self.api_handler = APIHandler(self._state)
        self.websocket_handler = WebSocketHandler()
        self.browser_handler = BrowserHandler()
        self.macro_handler = VirtualMacropadHandler(self._state)

    def _setup_routes(self):
        self.static_handler.setup_routes(self.app, "/static")
        self.page_handler.setup_routes(self.app, "/pages")
        self.api_handler.setup_routes(self.app, "/api")
        self.browser_handler.setup_routes(self.app, "")
        self.macro_handler.setup_routes(self.app, "")
        self.websocket_handler.setup_routes(self.app, "/ws")

    async def process(self):  # pragma: no cover
        try:
            runner = web.AppRunner(self.app, access_log=None)
            await runner.setup()
            _logger.info("WebServer setup complete")
            site = web.TCPSite(runner, self._host, self._port)
            _logger.debug("Starting WebServer at http://%s:%s", self._host, self._port)
            await site.start()
            _logger.info("WebServer running at http://%s:%s", self._host, self._port)
            self._running = True
        except Exception as e:
            _logger.error("Error starting WebServer: %s", e)
            self._running = False

    async def stop(self):  # pragma: no cover
        await self.app.shutdown()
        await self.app.cleanup()
        _logger.info("WebServer stopped")

    def register_callback(self, callback):
        self.websocket_handler.register_callback(callback)
        self.api_handler.register_callback(callback)

    async def send_msg(self, msg: HidOutputMessage):
        self.websocket_handler.send_msg(msg)
