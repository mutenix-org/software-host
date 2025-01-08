from __future__ import annotations

import asyncio
import webbrowser
from pathlib import Path

from mutenix.virtual_macropad import HOST
from mutenix.virtual_macropad import PORT
from PIL import Image
from pystray import Icon as icon
from pystray import Menu as menu
from pystray import MenuItem as item

def load_image(file_name):
    file_path = Path(__file__).parent / 'assets' / file_name
    return Image.open(file_path)

def run_trayicon(macropad):
    def open_macropad(icon, item):
        webbrowser.open(f"http://{HOST}:{PORT}")

    def quit_macropad(icon, item):
        asyncio.run(macropad.stop())
        icon.stop()

    icon(
        'MUTENIX', load_image('icon_all_red_64.png'), menu=menu(
            item(
                'Open Virtual Macropad',
                open_macropad,
            ),
            item(
                'Quit',
                quit_macropad,
            ),
        ),
    ).run()