# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
import json
from unittest import mock

import pytest
from aiohttp import web
from mutenix.models.hid_commands import HidOutputMessage
from mutenix.models.hid_commands import LedColor
from mutenix.models.hid_commands import SetLed
from mutenix.webserver.websocket import UnsupportedMessageTypeError
from mutenix.webserver.websocket import WebSocketHandler


@pytest.fixture
def websocket_handler():
    return WebSocketHandler()


@pytest.fixture
async def client(aiohttp_client, websocket_handler):
    app = web.Application()
    websocket_handler.setup_routes(app)
    return await aiohttp_client(app)


async def test_websocket_handler(client, websocket_handler):
    ws = await client.ws_connect("/ws")
    await ws.send_json({"command": "state_request"})
    websocket_handler._led_status = {1: "red"}
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            assert "button" in data
            assert "color" in data
            break
    await ws.close()


async def test_handle_state_request(websocket_handler):
    ws = mock.Mock()
    ws.send_json = mock.AsyncMock()
    websocket_handler._led_status = {1: "red", 2: "blue"}
    await websocket_handler.handle_state_request(ws)
    ws.send_json.assert_any_await({"button": 1, "color": "red"})
    ws.send_json.assert_any_await({"button": 2, "color": "blue"})


async def test_send_msg(websocket_handler):
    msg = SetLed(id=1, led_color=LedColor.RED)
    await websocket_handler.send_msg(msg)
    assert websocket_handler._led_status[1] == "red"


async def test_send_msg_unsupported(websocket_handler):
    msg = HidOutputMessage()
    with pytest.raises(UnsupportedMessageTypeError):
        await websocket_handler.send_msg(msg)


async def test_websocket_unknown_command(client):
    ws = await client.ws_connect("/ws")
    await ws.send_json({"command": "unknown"})
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            assert data["error"] == "unknown command"
            break
    await ws.close()


async def test_websocket_unknown_message(client):
    ws = await client.ws_connect("/ws")
    await ws.send_str("unknown message")
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            assert data["error"] == "unknown message"
            break
    await ws.close()
