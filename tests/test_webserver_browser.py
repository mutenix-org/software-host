import json
from pathlib import Path
from unittest import mock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from mutenix.webserver.browser import BrowserHandler


@pytest.fixture
def browser_handler():
    return BrowserHandler()


@pytest.fixture
def mock_assetpath(browser_handler):
    with mock.patch.object(browser_handler, "_assetpath", spec=Path) as mock_path:
        yield mock_path


async def test_serve_image(browser_handler, mock_assetpath):
    mock_assetpath.__truediv__.return_value = Path("/fake/path/image.png")
    request = make_mocked_request(
        "GET",
        "/web/images/image.png",
        match_info={"name": "image.png"},
    )
    with mock.patch(
        "aiohttp.web.FileResponse.__init__",
        return_value=None,
    ) as mock_init:
        mock_init.return_value = None
        response = await browser_handler.serve_image(request)
        assert isinstance(response, web.FileResponse)
        mock_init.assert_called_once_with(Path("/fake/path/image.png"))


async def test_favicon(browser_handler, mock_assetpath):
    mock_assetpath.__truediv__.return_value = Path("/fake/path/icon_active_16x16.png")
    request = make_mocked_request(
        "GET",
        "/web/favicon/16x16",
        match_info={"filename": "16"},
    )
    with mock.patch(
        "aiohttp.web.FileResponse.__init__",
        return_value=None,
    ) as mock_init:
        mock_init.return_value = None
        response = await browser_handler.favicon(request)
        assert isinstance(response, web.FileResponse)
        mock_init.assert_called_once_with(Path("/fake/path/icon_active_16x16.png"))


async def test_favicon_not_found(browser_handler):
    request = make_mocked_request(
        "GET",
        "/web/favicon/unknown",
        match_info={"filename": "unknown"},
    )
    with pytest.raises(web.HTTPNotFound):
        await browser_handler.favicon(request)


async def test_favicon_ico(browser_handler, mock_assetpath):
    mock_assetpath.__truediv__.return_value = Path("/fake/path/mutenix.ico")
    request = make_mocked_request("GET", "/web/favicon.ico")
    with mock.patch(
        "aiohttp.web.FileResponse.__init__",
        return_value=None,
    ) as mock_init:
        response = await browser_handler.favicon_ico(request)
        assert isinstance(response, web.FileResponse)
        mock_init.assert_called_once_with(Path("/fake/path/mutenix.ico"))


async def test_favicon_svg(browser_handler, mock_assetpath):
    mock_assetpath.__truediv__.return_value = Path(
        "/fake/path/mutenix_logo_finalicon_active.svg",
    )
    request = make_mocked_request("GET", "/web/favicon.svg")
    with mock.patch(
        "aiohttp.web.FileResponse.__init__",
        return_value=None,
    ) as mock_init:
        response = await browser_handler.favicon_svg(request)
        assert isinstance(response, web.FileResponse)
        mock_init.assert_called_once_with(
            Path("/fake/path/mutenix_logo_finalicon_active.svg"),
        )


async def test_serve_manifest(browser_handler):
    request = make_mocked_request("GET", "/web/site.webmanifest")
    response = await browser_handler.serve_manifest(request)
    assert response.status == 200
    manifest = json.loads(response.body)
    assert manifest["name"] == "Mutenix Virtual Macropad"
    assert manifest["short_name"] == "Mutenix"
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["icons"] == browser_handler.icons
