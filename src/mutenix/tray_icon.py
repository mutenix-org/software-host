from __future__ import annotations

import asyncio
import webbrowser
from pathlib import Path

from mutenix.macropad import Macropad
from PIL import Image


def load_image(file_name):
    file_path = Path(__file__).parent / "assets" / file_name
    return Image.open(file_path)


def run_trayicon(macropad: Macropad):  # pragma: no cover
    from pystray import Icon as icon, Menu as menu, MenuItem as item

    def open_url(endpoint=""):
        def open_url(icon, item):
            address = (
                macropad.virtual_keypad_address
                if macropad.virtual_keypad_address != "0.0.0.0"
                else "127.0.0.1"
            )
            webbrowser.open(
                f"http://{address}:{macropad.virtual_keypad_port}{endpoint}",
            )

        return open_url

    def quit_macropad(icon, item):
        asyncio.run(macropad.stop())
        icon.stop()

    icon(
        "MUTENIX",
        load_image("icon_all_red_64.png"),
        menu=menu(
            item(
                "Open Virtual Macropad",
                open_url("/"),
            ),
            item(
                "Help",
                open_url("/help"),
            ),
            item(
                "About",
                open_url("/about"),
            ),
            item(
                "Quit",
                quit_macropad,
            ),
        ),
    ).run()
