# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from collections import defaultdict
from unittest import mock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from mutenix.models.state import State
from mutenix.webserver.helper import Helper
from mutenix.webserver.pages import PageHandler


@pytest.fixture
def state():
    state = State()
    state.config.actions = []
    state.config.longpress_action = []
    state.config.leds = []
    state.hardware.version = "1.0"
    state.hardware.variant = "test_variant"
    return state


@pytest.fixture
def page_handler(state):
    return PageHandler(state)


async def test_help(page_handler):
    request = make_mocked_request("GET", "/pages/help")
    with mock.patch.object(
        Helper,
        "render_template",
        return_value=web.Response(text="help"),
    ) as mock_render:
        response = await page_handler.help(request)
        assert response.text == "help"
        mock_render.assert_called_once_with("help.html", request, {})


async def test_about(page_handler):
    request = make_mocked_request("GET", "/pages/about")
    with mock.patch.object(
        Helper,
        "render_template",
        return_value=web.Response(text="about"),
    ) as mock_render:
        with mock.patch.object(
            page_handler,
            "_read_markdown",
            side_effect=["readme content", "license content"],
        ):
            response = await page_handler.about(request)
            assert response.text == "about"
            mock_render.assert_called_once_with(
                "about.html",
                request,
                {
                    "readme_content": "readme content",
                    "license_content": "license content",
                },
            )


async def test_config(page_handler, state):
    request = make_mocked_request("GET", "/pages/config")
    with mock.patch.object(
        Helper,
        "render_template",
        return_value=web.Response(text="config"),
    ) as mock_render:
        response = await page_handler.config(request)
        assert response.text == "config"
        mock_render.assert_called_once()
        context = mock_render.call_args[0][2]
        assert isinstance(context["button_actions"], defaultdict)
        assert context["leds"] == state.config.leds
        assert "yaml_config" in context


async def test_device(page_handler, state):
    request = make_mocked_request("GET", "/pages/device")
    with mock.patch.object(
        Helper,
        "render_template",
        return_value=web.Response(text="device"),
    ) as mock_render:
        response = await page_handler.device(request)
        assert response.text == "device"
        mock_render.assert_called_once_with(
            "version.html",
            request,
            {
                "version": state.hardware.version,
                "hardware": state.hardware.variant,
            },
        )
