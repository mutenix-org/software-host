# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from aiohttp import web
from mutenix.webserver.helper import Helper


class VirtualMacropadHandler:
    def __init__(self, config):
        self._config = config

    async def handle_index(self, request: web.Request) -> web.Response:
        return Helper.render_template("index.html", request, {})

    async def handle_popup(self, request: web.Request) -> web.Response:
        return Helper.render_template("popup.html", request, {})

    def setup_routes(self, app: web.Application, prefix: str = "") -> None:
        app.router.add_route("GET", f"{prefix}/", self.handle_index)
        app.router.add_route("GET", f"{prefix}/popup", self.handle_popup)
