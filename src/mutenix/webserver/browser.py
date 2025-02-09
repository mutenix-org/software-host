import pathlib

from aiohttp import web


class BrowserHandler:
    _assetpath: pathlib.Path

    def __init__(self):
        self.icons: list[dict[str, str]] = [
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

        self._assetpath = pathlib.Path(__file__).parent.parent / "assets"

    async def _get_image(self, name: str):
        image_path = self._assetpath / f"{name}"
        return web.FileResponse(image_path)

    async def serve_image(self, request: web.Request):
        name = request.match_info["name"]
        return await self._get_image(name)

    async def favicon(self, request: web.Request):
        filename = request.match_info["filename"]
        for icon in self.icons:
            if icon["src"].endswith(filename):
                icon_response = await self._get_image(
                    f"icon_active_{icon['sizes']}.png",
                )
                break
        else:
            raise web.HTTPNotFound()
        return icon_response

    async def favicon_ico(self, request: web.Request):  # pragma: no cover
        return await self._get_image("mutenix.ico")

    async def favicon_svg(self, request: web.Request):
        return await self._get_image("mutenix_logo_finalicon_active.svg")

    async def serve_manifest(self, request: web.Request):
        manifest = {
            "name": "Mutenix Virtual Macropad",
            "short_name": "Mutenix",
            "icons": self.icons,
            "start_url": "/",
            "display": "standalone",
        }
        return web.json_response(manifest)

    def setup_routes(self, app: web.Application, prefix: str = "/web"):
        app.router.add_route("GET", f"{prefix}/favicon/{{filename}}", self.favicon)
        app.router.add_route("GET", f"{prefix}/favicon.svg", self.favicon_svg)
        app.router.add_route("GET", f"{prefix}/favicon.ico", self.favicon_ico)
        app.router.add_route("GET", f"{prefix}/site.webmanifest", self.serve_manifest)
        app.router.add_route("GET", f"{prefix}/images/{{name}}", self.serve_image)
