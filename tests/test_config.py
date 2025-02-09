# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import mock_open
from unittest.mock import patch

import yaml
from mutenix.config import CONFIG_FILENAME
from mutenix.config import find_config_file
from mutenix.config import load_config
from mutenix.config import save_config
from mutenix.models.config import Config


def test_find_config_file_default_location():
    with patch("pathlib.Path.exists", return_value=True):
        config_path = find_config_file()
        assert config_path == Path(CONFIG_FILENAME)


def test_find_config_file_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        config_path = find_config_file()
        assert config_path == Path(CONFIG_FILENAME)


def test_load_config_default():
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("builtins.open", mock_open(read_data="")),
        patch("mutenix.models.config.Config") as mock_create_default_config,
    ):
        default_config = Config()
        default_config._file_path = str(Path(CONFIG_FILENAME))
        mock_create_default_config.return_value = default_config
        config = load_config()
        assert (
            config.model_dump() == mock_create_default_config.return_value.model_dump()
        )


def test_load_config_file_not_found():
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("builtins.open", mock_open(read_data="")),
        patch("mutenix.models.config.Config") as mock_create_default_config,
        patch("mutenix.config.save_config") as mock_save_config,
    ):
        mock_create_default_config.return_value = Config()
        config = load_config()
        assert (
            config.model_dump() == mock_create_default_config.return_value.model_dump()
        )
        mock_save_config.assert_not_called()


def test_load_config_yaml_error():
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="invalid_yaml")),
        patch("yaml.safe_load", side_effect=yaml.YAMLError),
        patch("mutenix.models.config.Config") as mock_create_default_config,
        patch("mutenix.config.save_config") as mock_save_config,
    ):
        mock_create_default_config.return_value = Config()
        config = load_config()
        assert (
            config.model_dump() == mock_create_default_config.return_value.model_dump()
        )
        mock_save_config.assert_not_called()


def test_load_config_success():
    config_data = {
        "actions": [
            {"button_id": 1, "actions": [{"meeting_action": "toggle-mute"}]},
            {"button_id": 2, "actions": [{"meeting_action": "toggle-hand"}]},
        ],
        "longpress_action": [],
        "teams_token": None,
        "version": 1,
    }
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=yaml.dump(config_data))),
        patch("yaml.safe_load", return_value=config_data),
    ):
        config = load_config()
        assert config.model_dump() == Config(**config_data).model_dump()


def test_config_initialization():
    config_data = {
        "actions": [
            {"button_id": 1, "actions": [{"meeting_action": "toggle-mute"}]},
            {"button_id": 2, "actions": [{"meeting_action": "toggle-hand"}]},
        ],
        "longpress_action": [],
        "leds": [],
        "teams_token": None,
        "file_path": None,
        "virtual_keypad": {"bind_address": "127.0.0.1", "bind_port": 12909},
        "auto_update": True,
        "device_identifications": [],
    }
    config = Config(**config_data)
    assert config.actions[0].button_id == 1
    assert config.actions[0].actions[0].meeting_action == "toggle-mute"
    assert config.virtual_keypad.bind_address == "127.0.0.1"
    assert config.virtual_keypad.bind_port == 12909
    assert config.auto_update is True


def test_load_config_with_valid_file():
    config_data = {
        "actions": [
            {"button_id": 1, "actions": [{"meeting_action": "toggle-mute"}]},
            {"button_id": 2, "actions": [{"meeting_action": "toggle-hand"}]},
        ],
        "longpress_action": [],
        "leds": [],
        "teams_token": None,
        "file_path": None,
        "virtual_keypad": {"bind_address": "127.0.0.1", "bind_port": 12909},
        "auto_update": True,
        "device_identifications": [],
    }
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=yaml.dump(config_data))),
        patch("yaml.safe_load", return_value=config_data),
    ):
        config = load_config()
        assert config.actions[0].button_id == 1
        assert config.actions[0].actions[0].meeting_action == "toggle-mute"
        assert config.virtual_keypad.bind_address == "127.0.0.1"
        assert config.virtual_keypad.bind_port == 12909
        assert config.auto_update is True


def test_load_config_with_invalid_yaml():
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="invalid_yaml")),
        patch("yaml.safe_load", side_effect=yaml.YAMLError),
        patch("mutenix.models.config.Config") as mock_create_default_config,
        patch("mutenix.config.save_config") as mock_save_config,
    ):
        mock_create_default_config.return_value = Config()
        config = load_config()
        assert (
            config.model_dump() == mock_create_default_config.return_value.model_dump()
        )
        mock_save_config.assert_not_called()


def test_save_config():
    config = Config()
    with patch("pathlib.Path.open", mock_open()) as mocked_file:
        save_config(config, "test_config.yaml")
        mocked_file.assert_called_once_with("w")
        handle = mocked_file()
        handle.write.assert_called()


def test_find_config_file_in_current_directory():
    with patch("pathlib.Path.exists", side_effect=[True, False]):
        config_path = find_config_file()
        assert config_path == Path(CONFIG_FILENAME)


def test_find_config_file_in_home_directory():
    with patch("pathlib.Path.exists", side_effect=[False, True]):
        home_config_path = (
            Path.home() / os.environ.get("XDG_CONFIG_HOME", ".config") / CONFIG_FILENAME
        )
        config_path = find_config_file()
        assert config_path == home_config_path


def test_find_config_file_not_found_anywhere():
    with patch("pathlib.Path.exists", return_value=False):
        config_path = find_config_file()
        assert config_path == Path(CONFIG_FILENAME)


def test_load_config_with_file_path():
    config_data = {
        "actions": [
            {"button_id": 1, "actions": [{"meeting_action": "toggle-mute"}]},
            {"button_id": 2, "actions": [{"meeting_action": "toggle-hand"}]},
        ],
        "longpress_action": [],
        "leds": [],
        "teams_token": None,
        "file_path": None,
        "virtual_keypad": {"bind_address": "127.0.0.1", "bind_port": 12909},
        "auto_update": True,
        "device_identifications": [],
    }
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=yaml.dump(config_data))),
        patch("yaml.safe_load", return_value=config_data),
    ):
        config = load_config(Path("custom_config.yaml"))
        assert config.actions[0].button_id == 1
        assert config.actions[0].actions[0].meeting_action == "toggle-mute"
        assert config.virtual_keypad.bind_address == "127.0.0.1"
        assert config.virtual_keypad.bind_port == 12909
        assert config.auto_update is True
