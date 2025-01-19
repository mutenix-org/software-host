import pathlib

from aiohttp.test_utils import AioHTTPTestCase
from aiohttp.test_utils import unittest_run_loop
from mutenix.web_server import WebServer


class TestWebServer(AioHTTPTestCase):
    async def get_application(self):
        return WebServer().app

    @unittest_run_loop
    async def test_serve_image_success(self):
        image_name = "test_image.png"
        image_path = (
            pathlib.Path(__file__).parent.parent
            / "src"
            / "mutenix"
            / "assets"
            / image_name
        )
        image_path.touch()  # Create an empty file for testing

        request = await self.client.request("GET", f"/images/{image_name}")
        assert request.status == 200
        content = await request.read()
        assert content == image_path.read_bytes()

        image_path.unlink()  # Clean up the created file

    @unittest_run_loop
    async def test_serve_image_not_found(self):
        request = await self.client.request("GET", "/images/non_existent_image.png")
        assert request.status == 404
