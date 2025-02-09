# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
import pytest
from aiohttp import web
from mutenix.models.state import State
from mutenix.webserver.api import APIHandler


@pytest.fixture
def api_handler():
    state = State()
    state.hardware.variant = "test_variant"
    state.hardware.version = "1.0"
    handler = APIHandler(state)
    app = web.Application()
    handler.setup_routes(app)
    return app


@pytest.mark.asyncio
async def test_handle_invalid_button(aiohttp_client, api_handler):
    client = await aiohttp_client(api_handler)
    response = await client.post("/api/button", json={"button": "invalid"})
    assert response.status == 400


@pytest.mark.asyncio
async def test_handle_missing_button(aiohttp_client, api_handler):
    client = await aiohttp_client(api_handler)
    response = await client.post("/api/button", json={})
    assert response.status == 400


@pytest.mark.asyncio
async def test_handle_invalid_led_color(aiohttp_client, api_handler):
    client = await aiohttp_client(api_handler)
    response = await client.post(
        "/api/led",
        json={"button": 1, "color": "invalid_color"},
    )
    assert response.status == 400


@pytest.mark.asyncio
async def test_handle_missing_led_color(aiohttp_client, api_handler):
    client = await aiohttp_client(api_handler)
    response = await client.post("/api/led", json={"button": 1})
    assert response.status == 400


@pytest.mark.asyncio
async def test_handle_get_nonexistent_led(aiohttp_client, api_handler):
    client = await aiohttp_client(api_handler)
    response = await client.get("/api/led", params={"button": 999})
    assert response.status == 404


@pytest.mark.asyncio
async def test_handle_button(aiohttp_client, api_handler):
    client = await aiohttp_client(api_handler)
    response = await client.post("/api/button", json={"button": 1})
    assert response.status == 200


@pytest.mark.asyncio
async def test_handle_post_led(aiohttp_client, api_handler):
    client = await aiohttp_client(api_handler)
    response = await client.post("/api/led", json={"button": 1, "color": "red"})
    assert response.status == 200


@pytest.mark.asyncio
async def test_handle_get_led(aiohttp_client, api_handler):
    client = await aiohttp_client(api_handler)
    # First, set the LED color
    await client.post("/api/led", json={"button": 1, "color": "red"})
    # Then, get the LED color
    response = await client.get("/api/led", params={"button": 1})
    assert response.status == 200
    json_response = await response.json()
    assert json_response == {"button": 1, "color": "red"}
