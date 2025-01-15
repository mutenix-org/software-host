# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

from pathlib import Path
from unittest.mock import mock_open
from unittest.mock import patch

import yaml
from mutenix.config import Config
from mutenix.config import CONFIG_FILENAME
from mutenix.config import create_default_config
from mutenix.config import find_config_file
from mutenix.config import load_config


def test_find_config_file_default_location():
    with patch("pathlib.Path.exists", return_value=True):
        config_path = find_config_file()
        assert config_path == Path(CONFIG_FILENAME)


def test_find_config_file_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        config_path = find_config_file()
        assert config_path == Path(CONFIG_FILENAME)


def test_load_config_default():
    with patch("pathlib.Path.exists", return_value=False):
        with patch("builtins.open", mock_open(read_data="")):
            with patch(
                "mutenix.config.create_default_config",
            ) as mock_create_default_config:
                default_config = create_default_config()
                default_config.file_path = str(Path(CONFIG_FILENAME))
                mock_create_default_config.return_value = default_config
                config = load_config()
                assert config == mock_create_default_config.return_value


def test_load_config_file_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        with patch("builtins.open", mock_open(read_data="")):
            with patch(
                "mutenix.config.create_default_config",
            ) as mock_create_default_config:
                mock_create_default_config.return_value = create_default_config()
                with patch("mutenix.config.save_config") as mock_save_config:
                    config = load_config()
                    assert config == mock_create_default_config.return_value
                    mock_save_config.assert_called_once()


def test_load_config_yaml_error():
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="invalid_yaml")):
            with patch("yaml.safe_load", side_effect=yaml.YAMLError):
                with patch(
                    "mutenix.config.create_default_config",
                ) as mock_create_default_config:
                    mock_create_default_config.return_value = create_default_config()
                    with patch("mutenix.config.save_config") as mock_save_config:
                        config = load_config()
                        assert config == mock_create_default_config.return_value
                        mock_save_config.assert_called_once()


def test_load_config_success():
    config_data = {
        "actions": [
            {"button_id": 1, "action": "toggle-mute"},
            {"button_id": 2, "action": "toggle-hand"},
        ],
        "double_tap_action": [],
        "teams_token": None,
    }
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
            with patch("yaml.safe_load", return_value=config_data):
                config = load_config()
                assert config == Config(
                    **config_data,
                )
