

from aiohttp.test_utils import AioHTTPTestCase
from mutenix.virtual_macropad import VirtualMacropad
from mutenix.hid_commands import LedColor, SetLed
import asyncio

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
        assert "<html>" in text


    async def test_button_handler(self):
        data = {"button": 1}
        request = await self.client.request("POST", "/button", json=data)
        assert request.status == 200


    async def test_send_msg(self):
        msg = SetLed(id=1, led_color=LedColor.RED)
        self.macropad.send_msg(msg)
        assert self.macropad._led_status[1] == "red"


    async def test_process(self):
        await self.macropad.process()
        assert self.macropad.host == "127.0.0.1"
        assert self.macropad.port == 8080


    async def test_websocket_handler_button_press(self):
        self.start_process()
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({"button": 1})
        await ws.close()

    async def test_websocket_handler_state_request(self):
        self.start_process()
        self.macropad._led_status[1] = "red"
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({"state_request": True})
        msg = await ws.receive_json()
        assert "button" in msg
        assert "color" in msg
        await ws.close()

    async def test_websocket_handler_multiple_clients(self):
        self.start_process()
        self.macropad._led_status[1] = "red"
        ws1 = await self.client.ws_connect("/ws")
        ws2 = await self.client.ws_connect("/ws")
        self.macropad.send_msg(SetLed(id=2, led_color=LedColor.GREEN))
        msg1 = await ws1.receive_json()
        msg2 = await ws2.receive_json()
        assert msg1["button"] == 2
        assert msg2["button"] == 2
        await ws1.close()
        await ws2.close()
