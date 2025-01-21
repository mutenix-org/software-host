# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import logging
import pathlib

import jinja2
import markdown
import yaml
from aiohttp import web
from aiohttp_jinja2 import render_template
from aiohttp_jinja2 import setup as jinja2_setup

HOST = "127.0.0.1"
PORT = 12909

_logger = logging.getLogger(__name__)


class WebServer:
    """A general web server class for serving web pages and static content."""

    icons: list[dict[str, str]] = [
        {
            "src": "/favicon/32",
            "sizes": "32x32",
            "type": "image/png",
        },
        {
            "src": "/favicon/64",
            "sizes": "64x64",
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
        self._running = False
        self.app = web.Application()
        self.app.router.add_static(
            "/static/",
            path=str(pathlib.Path(__file__).parent / "static"),
            name="static",
        )
        self.app.router.add_route("GET", "/favicon/{filename}", self.favicon)
        self.app.router.add_route("GET", "/favicon.svg", self.favicon_svg)
        self.app.router.add_route("GET", "/favicon.ico", self.favicon_ico)
        self.app.router.add_route("GET", "/site.webmanifest", self.serve_manifest)
        self.app.router.add_route("GET", "/images/{name}", self.serve_image)
        self.app.router.add_route("GET", "/help", self.help)
        self.app.router.add_route("GET", "/about", self.about)
        self.app.router.add_route("GET", "/config", self.config)
        self.app.add_routes(
            [
                web.get("/", self.index),
                web.get("/popup", self.popup),
            ],
        )
        jinja2_setup(self.app, loader=jinja2.PackageLoader("mutenix", "templates"))

    def update_config(self, config):
        self._config = config

    async def index(self, request: web.Request):
        return render_template("index.html", request, {})

    async def popup(self, request: web.Request):
        return render_template("popup.html", request, {})

    async def serve_image(self, request: web.Request):
        name = request.match_info["name"]
        image_path = pathlib.Path(__file__).parent / "assets" / f"{name}"
        return web.FileResponse(image_path)

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

    async def favicon_ico(self, request: web.Request):  # pragma: no cover
        return web.FileResponse(
            pathlib.Path(__file__).parent / "assets" / "mutenix.ico",
        )

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
        readme_path = pathlib.Path(__file__).parent / "README.md"
        license_path = pathlib.Path(__file__).parent / "LICENSE"
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
        with open(license_path, "r", encoding="utf-8") as f:
            license_content = f.read()
        html_readme_content = markdown.markdown(
            readme_content,
            extensions=["fenced_code", "tables"],
        )
        html_license_content = markdown.markdown(license_content)
        context = {
            "readme_content": html_readme_content,
            "license_content": html_license_content,
        }
        return render_template("about.html", request, context)

    async def config(self, request: web.Request):
        context = {
            "button_actions": self._config.actions,
            "leds": self._config.leds,
            "yaml_config": yaml.dump(self._config.model_dump(mode="json")),
        }
        return render_template("config.html", request, context)

    async def process(self):
        try:
            runner = web.AppRunner(self.app, access_log=None)
            await runner.setup()
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
            _logger.info("WebServer running at http://%s:%s", self.host, self.port)
            self._running = True
        except Exception as e:
            _logger.error("Error starting WebServer: %s", e)
            self._running = False

    async def stop(self):
        await self.app.shutdown()
        await self.app.cleanup()
        _logger.info("WebServer stopped")
