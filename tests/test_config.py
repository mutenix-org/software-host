from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mutenix.config import CONFIG_FILENAME
from mutenix.config import find_config_file


def test_find_config_file_default_location():
    with patch("pathlib.Path.exists", return_value=True):
        config_path = find_config_file()
        assert config_path == Path(CONFIG_FILENAME)


def test_find_config_file_home_config_location():
    with patch("pathlib.Path.exists", side_effect=[False, True]):
        with patch("pathlib.Path.home", return_value=Path("/mock/home")):
            config_path = find_config_file()
            expected_path = Path("/mock/home/.config") / CONFIG_FILENAME
            assert config_path == expected_path


def test_find_config_file_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        config_path = find_config_file()
        assert config_path == Path(CONFIG_FILENAME)
