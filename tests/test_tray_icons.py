# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

from mutenix.tray_icon import load_image


def test_load_image_file_not_found():
    file_name = "non_existent_image.png"
    load_image(file_name)
