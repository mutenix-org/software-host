# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
import pathlib

from aiohttp import web


class StaticHandler:
    def __init__(self):
        self.static_path = str(pathlib.Path(__file__).parent.parent / "static")

    def setup_routes(self, app: web.Application, prefix: str = "/static") -> None:
        app.router.add_static(f"{prefix}/", path=self.static_path, name="static")
