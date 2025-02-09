# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from mutenix.updates.device_messages import LogMessage


def test_log_message_valid_debug():
    data = b"LDThis is a debug message\x00"
    log_message = LogMessage(data)
    assert log_message.is_valid
    assert log_message.level == "debug"
    assert log_message.message == "This is a debug message"
    assert str(log_message) == "debug: This is a debug message"


def test_log_message_valid_error():
    data = b"LEThis is an error message\x00"
    log_message = LogMessage(data)
    assert log_message.is_valid
    assert log_message.level == "error"
    assert log_message.message == "This is an error message"
    assert str(log_message) == "error: This is an error message"


def test_log_message_invalid_identifier():
    data = b"XXInvalid identifier\x00"
    log_message = LogMessage(data)
    assert not log_message.is_valid
    assert log_message.message == ""
    assert str(log_message) == "Invalid Request"


def test_log_message_no_null_terminator():
    data = b"LEThis is an error message"
    log_message = LogMessage(data)
    assert log_message.is_valid
    assert log_message.level == "error"
    assert log_message.message == "This is an error message"
    assert str(log_message) == "error: This is an error message"


def test_log_message_empty_data():
    data = b""
    log_message = LogMessage(data)
    assert not log_message.is_valid
    assert log_message.message == ""
    assert str(log_message) == "Invalid Request"
