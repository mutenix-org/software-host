# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

from pathlib import Path
from unittest.mock import mock_open
from unittest.mock import patch

import pytest
from mutenix.tray_icon import load_image


def test_load_image_success():
    file_name = "test_image.png"
    file_path = Path(__file__).parent.parent / "src" / "mutenix" / "assets" / file_name

    with patch(
        "mutenix.tray_icon.Path.open",
        mock_open(read_data="image_data"),
    ):
        with patch("PIL.Image.open") as mock_image_open:
            load_image(file_name)
            mock_image_open.assert_called_once_with(file_path)


def test_load_image_file_not_found():
    file_name = "non_existent_image.png"
    with pytest.raises(FileNotFoundError):
        load_image(file_name)
