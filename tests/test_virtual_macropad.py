# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

import asyncio
from unittest.mock import ANY
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from aiohttp.test_utils import AioHTTPTestCase
from mutenix.hid_commands import HidOutputMessage
from mutenix.hid_commands import LedColor
from mutenix.hid_commands import SetLed
from mutenix.hid_commands import Status
from mutenix.virtual_macropad import UnsupportedMessageTypeError
from mutenix.virtual_macropad import VirtualMacropad


class TestVirtualMacropad(AioHTTPTestCase):
    async def get_application(self):
        self.macropad = VirtualMacropad()
        return self.macropad.app

    def start_process(self):
        async def start_process():
            while True:
                await self.macropad.process()
                await asyncio.sleep(0.1)

        self.loop.create_task(start_process())

    async def test_index(self):
        request = await self.client.request("GET", "/")
        assert request.status == 200
        text = await request.text()
        assert "<!DOCTYPE html PUBLIC" in text

    async def test_button_handler(self):
        data = {"button": 1}
        request = await self.client.request("POST", "/button", json=data)
        assert request.status == 200

    async def test_send_msg(self):
        msg = SetLed(id=1, led_color=LedColor.RED)
        await self.macropad.send_msg(msg)
        async with self.macropad._led_status_lock:
            assert self.macropad._led_status[1] == "red"

    async def test_send_msg_invalid(self):
        class SomeMessage(HidOutputMessage):
            pass

        msg = SomeMessage()
        with pytest.raises(UnsupportedMessageTypeError):
            await self.macropad.send_msg(msg)

    async def test_process(self):
        await self.macropad.process()
        assert self.macropad.host == "127.0.0.1"
        assert self.macropad.port == 12909

    async def test_websocket_handler_button_press(self):
        self.start_process()
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({"command": "button", "button": 1})
        await ws.close()

    async def test_websocket_handler_state_request(self):
        self.start_process()
        self.macropad._led_status[1] = "red"
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({"command": "state_request"})
        msg = await ws.receive_json()
        assert "button" in msg
        assert "color" in msg
        await ws.close()

    async def test_websocket_handler_unknown(self):
        self.start_process()
        self.macropad._led_status[1] = "red"
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({"command": "something_else"})
        msg = await ws.receive_json()
        assert "error" in msg
        await ws.close()

    async def test_websocket_handler_multiple_clients(self):
        self.start_process()
        self.macropad._led_status[1] = "red"
        ws1 = await self.client.ws_connect("/ws")
        ws2 = await self.client.ws_connect("/ws")
        await self.macropad.send_msg(SetLed(id=2, led_color=LedColor.GREEN))
        msg1 = await ws1.receive_json()
        msg2 = await ws2.receive_json()
        assert msg1["button"] == 2
        assert msg2["button"] == 2
        await ws1.close()
        await ws2.close()

    @pytest.mark.asyncio
    async def test_send_json_safe_success(self):
        ws = AsyncMock()
        data = {"button": 1, "color": "red"}
        await self.macropad._send_json_safe(ws, data)
        ws.send_json.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_send_json_safe_failure(self):
        ws = AsyncMock()
        ws.send_json.side_effect = Exception("Test exception")
        data = {"button": 1, "color": "red"}
        with patch("mutenix.virtual_macropad._logger.error") as mock_logger_error:
            await self.macropad._send_json_safe(ws, data)
            ws.send_json.assert_called_once_with(data)
            mock_logger_error.assert_called_once_with(
                "Error sending LED status: %s to websocket %s",
                ANY,
                ANY,
            )

    async def test_register_callback(self):
        callback = AsyncMock()
        self.macropad.register_callback(callback)
        await self.macropad._handle_msg(Status.trigger_button(1))
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self):
        self.macropad.app.shutdown = AsyncMock()
        self.macropad.app.cleanup = AsyncMock()
        await self.macropad.stop()
        self.macropad.app.shutdown.assert_called_once()
        self.macropad.app.cleanup.assert_called_once()

    async def test_favicon_32(self):
        request = await self.client.request("GET", "/favicon/32")
        assert request.status == 200
        assert request.content_type == "image/png"

    async def test_favicon_16(self):
        request = await self.client.request("GET", "/favicon/16")
        assert request.status == 200
        assert request.content_type == "image/png"

    async def test_favicon_apple_touch(self):
        request = await self.client.request("GET", "/favicon/apple_touch")
        assert request.status == 200
        assert request.content_type == "image/png"

    async def test_favicon_not_found(self):
        request = await self.client.request("GET", "/favicon/non_existent")
        assert request.status == 404

    async def test_favicon_svg(self):
        request = await self.client.request("GET", "/favicon.svg")
        assert request.status == 200
        assert request.content_type == "image/svg+xml"

    async def test_serve_manifest(self):
        request = await self.client.request("GET", "/site.webmanifest")
        assert request.status == 200
        manifest = await request.json()
        assert manifest["name"] == "Mutenix Virtual Macropad"
        assert manifest["short_name"] == "Mutenix"
        assert manifest["start_url"] == "/"
        assert manifest["display"] == "standalone"
        assert len(manifest["icons"]) == 3
        assert manifest["icons"][0]["src"] == "/favicon/32"
        assert manifest["icons"][1]["src"] == "/favicon/16"
        assert manifest["icons"][2]["src"] == "/favicon/apple_touch"

    async def test_help(self):
        request = await self.client.request("GET", "/help")
        assert request.status == 200
        text = await request.text()
        assert "Help" in text

    async def test_about(self):
        request = await self.client.request("GET", "/about")
        assert request.status == 200
        text = await request.text()
        assert "About" in text

    async def test_websocket_handler_non_text_message(self):
        self.start_process()
        ws = await self.client.ws_connect("/ws")
        await ws.send_bytes(b"binary data")
        msg = await ws.receive_json()
        assert "error" in msg
        assert msg["error"] == "unknown message"
        await ws.close()
