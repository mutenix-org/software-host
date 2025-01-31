# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import mock_open
from unittest.mock import patch

import yaml
from mutenix.config import ActionEnum
from mutenix.config import button_action_details_descriminator
from mutenix.config import ButtonAction
from mutenix.config import Config
from mutenix.config import CONFIG_FILENAME
from mutenix.config import create_default_config
from mutenix.config import find_config_file
from mutenix.config import KeyPress
from mutenix.config import load_config
from mutenix.config import MouseActionClick
from mutenix.config import save_config
from mutenix.config import WebhookAction
from mutenix.teams_messages import MeetingAction


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
                    mock_save_config.assert_not_called()


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
                    mock_save_config.assert_not_called()


def test_load_config_success():
    config_data = {
        "actions": [
            {"button_id": 1, "action": "toggle-mute"},
            {"button_id": 2, "action": "toggle-hand"},
        ],
        "longpress_action": [],
        "teams_token": None,
    }
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
            with patch("yaml.safe_load", return_value=config_data):
                config = load_config()
                assert config == Config(
                    **config_data,
                )


def test_config_initialization():
    config_data = {
        "actions": [
            {"button_id": 1, "action": "toggle-mute"},
            {"button_id": 2, "action": "toggle-hand"},
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
    assert config.actions[0].action == "toggle-mute"
    assert config.virtual_keypad.bind_address == "127.0.0.1"
    assert config.virtual_keypad.bind_port == 12909
    assert config.auto_update is True


def test_load_config_with_valid_file():
    config_data = {
        "actions": [
            {"button_id": 1, "action": "toggle-mute"},
            {"button_id": 2, "action": "toggle-hand"},
        ],
        "longpress_action": [],
        "leds": [],
        "teams_token": None,
        "file_path": None,
        "virtual_keypad": {"bind_address": "127.0.0.1", "bind_port": 12909},
        "auto_update": True,
        "device_identifications": [],
    }
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
            with patch("yaml.safe_load", return_value=config_data):
                config = load_config()
                assert config.actions[0].button_id == 1
                assert config.actions[0].action == "toggle-mute"
                assert config.virtual_keypad.bind_address == "127.0.0.1"
                assert config.virtual_keypad.bind_port == 12909
                assert config.auto_update is True


def test_load_config_with_invalid_yaml():
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
                        mock_save_config.assert_not_called()


def test_save_config():
    config = create_default_config()
    with patch("builtins.open", mock_open()) as mocked_file:
        save_config(config, "test_config.yaml")
        mocked_file.assert_called_once_with("test_config.yaml", "w")
        handle = mocked_file()
        handle.write.assert_called()


def test_button_action_with_none_extra():
    action = ButtonAction(button_id=1, action=MeetingAction.ToggleMute)
    assert action.button_id == 1
    assert action.action == MeetingAction.ToggleMute
    assert action.extra is None


def test_button_action_with_react_extra():
    action = ButtonAction(button_id=1, action=MeetingAction.React, extra="like")
    assert action.button_id == 1
    assert action.action == MeetingAction.React
    assert action.extra == "like"


def test_button_action_with_sequence_extra():
    sequence = [
        MouseActionClick(action="click", button="left").model_dump(),
        MouseActionClick(action="click", button="left").model_dump(),
    ]
    action = ButtonAction(button_id=1, action=ActionEnum.CMD, extra=sequence)
    assert action.button_id == 1
    assert action.action == ActionEnum.CMD
    assert len(action.extra) == 2


def test_button_action_with_single_keypress_extra():
    keypress = KeyPress(modifiers=["ctrl"], key="a")
    keypress_extra = keypress.model_dump()
    action = ButtonAction(button_id=1, action=ActionEnum.KEYPRESS, extra=keypress_extra)
    assert action.button_id == 1
    assert action.action == ActionEnum.KEYPRESS
    assert action.extra == keypress


def test_button_action_with_single_mouse_action_extra():
    mouse_action = MouseActionClick(action="click", button="left")
    mouse_action_extra = mouse_action.model_dump()
    action = ButtonAction(
        button_id=1,
        action=ActionEnum.MOUSE,
        extra=mouse_action_extra,
    )
    assert action.button_id == 1
    assert action.action == ActionEnum.MOUSE
    assert action.extra == mouse_action


def test_button_action_with_webhook_extra():
    webhook = WebhookAction(
        method="POST",
        url="http://example.com",
        headers={"Content-Type": "application/json"},
        data={"key": "value"},
    )
    webhook_extra = webhook.model_dump()
    action = ButtonAction(button_id=1, action=ActionEnum.WEBHOOK, extra=webhook_extra)
    assert action.button_id == 1
    assert action.action == ActionEnum.WEBHOOK
    assert action.extra == webhook


def test_button_action_details_descriminator_cmd():
    assert button_action_details_descriminator("some_command") == "cmd"


def test_button_action_details_descriminator_key():
    keypress = {"key": "a", "modifiers": ["ctrl"]}
    assert button_action_details_descriminator(keypress) == "key"


def test_button_action_details_descriminator_mouse():
    mouse_action = {"x": 100, "y": 200, "button": "left"}
    assert button_action_details_descriminator(mouse_action) == "mouse"


def test_button_action_details_descriminator_webhook():
    webhook_action = {"url": "http://example.com", "method": "POST"}
    assert button_action_details_descriminator(webhook_action) == "webhook"


def test_button_action_details_descriminator_empty_dict():
    assert button_action_details_descriminator({}) == ""


def test_button_action_details_descriminator_invalid_type():
    assert button_action_details_descriminator(123) == ""


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
            {"button_id": 1, "action": "toggle-mute"},
            {"button_id": 2, "action": "toggle-hand"},
        ],
        "longpress_action": [],
        "leds": [],
        "teams_token": None,
        "file_path": None,
        "virtual_keypad": {"bind_address": "127.0.0.1", "bind_port": 12909},
        "auto_update": True,
        "device_identifications": [],
    }
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=yaml.dump(config_data))):
            with patch("yaml.safe_load", return_value=config_data):
                config = load_config(Path("custom_config.yaml"))
                assert config.actions[0].button_id == 1
                assert config.actions[0].action == "toggle-mute"
                assert config.virtual_keypad.bind_address == "127.0.0.1"
                assert config.virtual_keypad.bind_port == 12909
                assert config.auto_update is True
