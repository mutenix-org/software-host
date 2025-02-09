# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from unittest import mock

import pytest
from mutenix.actions import _do_run_command
from mutenix.actions import keyboard_action
from mutenix.actions import mouse_action
from mutenix.actions import webhook_action
from mutenix.models.config import Key
from mutenix.models.config import Keyboard
from mutenix.models.config import KeyTap
from mutenix.models.config import KeyType
from mutenix.models.config import Mouse
from mutenix.models.config import MouseButton
from mutenix.models.config import MousePosition
from mutenix.models.config import WebhookAction


@pytest.fixture
def mock_keyboard_controller():
    with mock.patch("mutenix.actions.Controller") as MockController:
        yield MockController


@pytest.fixture
def mock_mouse_controller():
    with mock.patch("mutenix.actions.MouseController") as MockMouseController:
        yield MockMouseController


@pytest.fixture
def mock_button():
    with mock.patch("mutenix.actions.Button") as MockButton:
        yield MockButton


@pytest.fixture
def mock_key():
    with mock.patch("mutenix.actions.Key") as MockButton:
        yield MockButton


@pytest.fixture
def mock_requests_session():
    with mock.patch("mutenix.actions._session") as MockSession:
        yield MockSession


def test_keyboard_action_press(mock_keyboard_controller):
    action = Keyboard(press=Key(key="a"))
    keyboard_action(action)
    mock_keyboard_controller().press.assert_called_once_with("a")


def test_keyboard_action_release(mock_keyboard_controller):
    action = Keyboard(release=Key(key="a"))
    keyboard_action(action)
    mock_keyboard_controller().release.assert_called_once_with("a")


def test_keyboard_action_tap(mock_keyboard_controller):
    action = Keyboard(tap=KeyTap(key="a", modifiers=["ctrl"]))
    keyboard_action(action)
    mock_keyboard_controller().press.assert_any_call("ctrl")
    mock_keyboard_controller().tap.assert_called_once_with("a")
    mock_keyboard_controller().release.assert_any_call("ctrl")


def test_keyboard_action_type(mock_keyboard_controller):
    action = Keyboard(type=KeyType(string="hello"))
    keyboard_action(action)
    mock_keyboard_controller().type.assert_called_once_with("hello")


def test_mouse_action_move(mock_mouse_controller):
    action = Mouse(move=MousePosition(x=100, y=200))
    mouse_action(action)
    mock_mouse_controller().move.assert_called_once_with(100, 200)


def test_mouse_action_click(mock_mouse_controller, mock_button):
    action = Mouse(click=MouseButton(button="left"))
    mock_button.left = 1
    mouse_action(action)
    mock_mouse_controller().click.assert_called_once_with(mock.ANY, 1)


def test_mouse_action_set(mock_mouse_controller):
    action = Mouse(set=MousePosition(x=100, y=200))
    mouse_action(action)
    mock_mouse_controller().position = (100, 200)


def test_mouse_action_press(mock_mouse_controller, mock_button):
    action = Mouse(press=MouseButton(button="left"))
    mock_button.left = 1
    mouse_action(action)
    mock_mouse_controller().press.assert_called_once_with(1)


def test_mouse_action_release(mock_mouse_controller, mock_button):
    action = Mouse(release=MouseButton(button="left"))
    mock_button.left = 1
    mouse_action(action)
    mock_mouse_controller().release.assert_called_once_with(1)


def test_webhook_action(mock_requests_session):
    webhook = WebhookAction(
        method="POST",
        url="http://example.com",
        data={"key": "value"},
        params={"param": "value"},
        headers={"header": "value"},
    )
    webhook_action(webhook)
    mock_requests_session.request.assert_called_once_with(
        "POST",
        "http://example.com",
        json={"key": "value"},
        params={"param": "value"},
        headers={"header": "value"},
    )


def test_do_run_command_success():
    with mock.patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = mock.Mock(
            stdout="output",
            stderr="",
            returncode=0,
        )
        _do_run_command("echo test")
        mock_subprocess_run.assert_called_once_with(
            ["echo", "test"],
            capture_output=True,
            text=True,
        )


def test_do_run_command_failure():
    with mock.patch("subprocess.run") as mock_subprocess_run:
        mock_subprocess_run.return_value = mock.Mock(
            stdout="",
            stderr="error",
            returncode=1,
        )
        _do_run_command("invalid_command")
        mock_subprocess_run.assert_called_once_with(
            ["invalid_command"],
            capture_output=True,
            text=True,
        )


def test_webhook_action_get(mock_requests_session):
    webhook = WebhookAction(
        method="GET",
        url="http://example.com",
        data=None,
        params={"param": "value"},
        headers={"header": "value"},
    )
    webhook_action(webhook)
    mock_requests_session.request.assert_called_once_with(
        "GET",
        "http://example.com",
        json=None,
        params={"param": "value"},
        headers={"header": "value"},
    )


def test_webhook_action_put(mock_requests_session):
    webhook = WebhookAction(
        method="PUT",
        url="http://example.com",
        data={"key": "value"},
        params={"param": "value"},
        headers={"header": "value"},
    )
    webhook_action(webhook)
    mock_requests_session.request.assert_called_once_with(
        "PUT",
        "http://example.com",
        json={"key": "value"},
        params={"param": "value"},
        headers={"header": "value"},
    )


def test_webhook_action_delete(mock_requests_session):
    webhook = WebhookAction(
        method="DELETE",
        url="http://example.com",
        data=None,
        params={"param": "value"},
        headers={"header": "value"},
    )
    webhook_action(webhook)
    mock_requests_session.request.assert_called_once_with(
        "DELETE",
        "http://example.com",
        json=None,
        params={"param": "value"},
        headers={"header": "value"},
    )


def test_webhook_action_exception(mock_requests_session):
    mock_requests_session.request.side_effect = Exception("Network error")
    webhook = WebhookAction(
        method="POST",
        url="http://example.com",
        data={"key": "value"},
        params={"param": "value"},
        headers={"header": "value"},
    )
    webhook_action(webhook)
    mock_requests_session.request.assert_called_once_with(
        "POST",
        "http://example.com",
        json={"key": "value"},
        params={"param": "value"},
        headers={"header": "value"},
    )
