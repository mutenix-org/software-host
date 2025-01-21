# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import logging
import webbrowser
from pathlib import Path
from typing import Any

from mutenix.macropad import Macropad
from PIL import Image

my_icon: Any | None = None
_logger = logging.getLogger(__name__)


def load_image(file_name):
    try:
        file_path = Path(__file__).parent / "assets" / file_name
        return Image.open(file_path)
    except Exception as e:
        _logger.error("Error loading image: %s", e)
        return Image.new("RGB", (64, 64), "red")


def run_trayicon(macropad: Macropad):  # pragma: no cover
    global my_icon
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

    def activate_serial_console(icon, item):
        macropad.activate_serial_console()

    def deactivate_serial_console(icon, item):
        macropad.deactivate_serial_console()

    def activate_filesystem(icon, item):
        macropad.activate_filesystem()

    def quit_macropad(icon, item):
        icon.stop()
        asyncio.run(macropad.stop())

    def nothing(icon, item):
        pass

    my_icon = icon(
        "MUTENIX",
        load_image("icon_all_red_64.png"),
        menu=menu(
            item(
                "Open Virtual Macropad",
                open_url("/"),
            ),
            item(
                "Reload Config",
                macropad.reload_config,
            ),
            item(
                "Teams connected",
                nothing,
                checked=lambda x: macropad.teams_connected,
                enabled=False,
            ),
            item(
                "Device connected",
                nothing,
                checked=lambda x: macropad.device_connected,
                enabled=False,
            ),
            item(
                "Show Config",
                open_url("/config"),
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
                "Debug Options",
                menu(
                    item("Activate Serial Console", activate_serial_console),
                    item("Deactivate Serial Console", deactivate_serial_console),
                    item("Activate Filesystem", activate_filesystem),
                ),
            ),
            item(
                "Quit",
                quit_macropad,
            ),
        ),
    )
    my_icon.run()
