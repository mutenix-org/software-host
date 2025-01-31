# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

import pytest
from mutenix.hid_commands import HidInCommands
from mutenix.hid_commands import HidInputMessage
from mutenix.hid_commands import HidOutCommands
from mutenix.hid_commands import LedColor
from mutenix.hid_commands import Reset
from mutenix.hid_commands import SetLed
from mutenix.hid_commands import Status
from mutenix.hid_commands import StatusRequest
from mutenix.hid_commands import UpdateConfig
from mutenix.hid_commands import VersionInfo


def test_status():
    buffer = bytes([1, 1, 0, 0, 1])
    status = Status(buffer)
    assert status.button == 1
    assert status.triggered is True
    assert status.longpressed is False
    assert status.pressed is False
    assert status.released is True


def test_version_info():
    buffer = bytes([1, 0, 0, 3])
    version_info = VersionInfo(buffer)
    assert version_info.version == "1.0.0"
    assert version_info.type.name == "FIVE_BUTTON_USB"


def test_reset():
    reset = Reset()
    buffer = reset.to_buffer()
    assert buffer[:-1] == bytes([HidOutCommands.RESET, 0, 0, 0, 0, 0, 0, 0])[:-1]


def test_set_led():
    led = SetLed(1, LedColor.RED)
    buffer = led.to_buffer()
    assert (
        buffer[:-1]
        == bytes([HidOutCommands.SET_LED, 1, 0x00, 0x0A, 0x00, 0x00, 0, 0])[:-1]
    )


def test_from_buffer_version_info():
    buffer = bytes([0, HidInCommands.VERSION_INFO, 1, 2, 3, 4, 5, 6])
    message = HidInputMessage.from_buffer(buffer)
    assert isinstance(message, VersionInfo)
    assert message.buffer == buffer[2:8]


def test_from_buffer_status():
    buffer = bytes([0, HidInCommands.STATUS, 1, 0, 0, 1, 0, 0])
    message = HidInputMessage.from_buffer(buffer)
    assert isinstance(message, Status)
    assert message.buffer == buffer[2:8]


def test_from_buffer_status_request():
    buffer = bytes([0, HidInCommands.STATUS_REQUEST.value, 0, 0, 0, 0, 0, 0])
    message = HidInputMessage.from_buffer(buffer)
    assert isinstance(message, StatusRequest)


def test_from_buffer_not_implemented():
    buffer = bytes([0, 0xFF, 0, 0, 0, 0, 0, 0])
    with pytest.raises(NotImplementedError):
        HidInputMessage.from_buffer(buffer)


def test_update_config_to_buffer_default():
    update_config = UpdateConfig()
    buffer = update_config.to_buffer()
    assert (
        buffer[:-1] == bytes([HidOutCommands.UPDATE_CONFIG, 0, 0, 0, 0, 0, 0, 0])[:-1]
    )


def test_update_config_to_buffer_debug():
    update_config = UpdateConfig()
    update_config.activate_debug(True)
    buffer = update_config.to_buffer()
    assert (
        buffer[:-1] == bytes([HidOutCommands.UPDATE_CONFIG, 2, 0, 0, 0, 0, 0, 0])[:-1]
    )


def test_update_config_to_buffer_filesystem():
    update_config = UpdateConfig()
    update_config.activate_filesystem(True)
    buffer = update_config.to_buffer()
    assert (
        buffer[:-1] == bytes([HidOutCommands.UPDATE_CONFIG, 0, 2, 0, 0, 0, 0, 0])[:-1]
    )


def test_update_config_to_buffer_debug_and_filesystem():
    update_config = UpdateConfig()
    update_config.activate_debug(True)
    update_config.activate_filesystem(True)
    buffer = update_config.to_buffer()
    assert (
        buffer[:-1] == bytes([HidOutCommands.UPDATE_CONFIG, 2, 2, 0, 0, 0, 0, 0])[:-1]
    )


def test_update_config_str_default():
    update_config = UpdateConfig()
    assert str(update_config) == "UpdateConfig { debug: 0, filesystem: 0 }"


def test_update_config_str_debug():
    update_config = UpdateConfig()
    update_config.activate_debug(True)
    assert str(update_config) == "UpdateConfig { debug: 2, filesystem: 0 }"


def test_update_config_str_filesystem():
    update_config = UpdateConfig()
    update_config.activate_filesystem(True)
    assert str(update_config) == "UpdateConfig { debug: 0, filesystem: 2 }"


def test_update_config_str_debug_and_filesystem():
    update_config = UpdateConfig()
    update_config.activate_debug(True)
    update_config.activate_filesystem(True)
    assert str(update_config) == "UpdateConfig { debug: 2, filesystem: 2 }"
