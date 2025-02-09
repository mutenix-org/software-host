# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import logging
import shlex
import subprocess

import requests
from mutenix.models.config import Keyboard
from mutenix.models.config import Mouse
from mutenix.models.config import WebhookAction

try:
    from pynput.keyboard import Controller
    from pynput.keyboard import Key
    from pynput.mouse import Button
    from pynput.mouse import Controller as MouseController
except ImportError:  # pragma: no cover
    Key = None
    Button = None
    MouseController = None
    Controller = None

_logger = logging.getLogger(__name__)
_session = requests.Session()


def keyboard_action(action: Keyboard) -> None:
    if not Controller:
        _logger.error("pynput not supported, cannot send keypress")
        return

    keyboard = Controller()
    if action.release:
        _logger.debug("Stop Pressing: %s", action.release.key)
        keyboard.release(action.release.key)
    elif action.press:
        _logger.debug("Start Pressing: %s", action.press.key)
        keyboard.press(action.press.key)
    elif action.tap:
        _logger.debug(
            "Tap %s",
            " + ".join(action.tap.modifiers + [action.tap.key]),
        )
        for key in action.tap.modifiers:
            keyboard.press(key)
        keyboard.tap(action.tap.key)
        for key in reversed(action.tap.modifiers):
            keyboard.release(key)
    elif action.type:
        _logger.debug("Type %s", action.type.string)
        keyboard.type(action.type.string)


def mouse_action(action: Mouse) -> None:
    if not MouseController:
        _logger.error("pynput not supported, cannot send mousemove")
        return
    mouse = MouseController()
    if action.move:
        _logger.debug("Move mouse to %s, %s", action.move.x, action.move.y)
        mouse.move(action.move.x, action.move.y)
    elif action.set:
        _logger.debug("Set mouse to %s, %s", action.set.x, action.set.y)
        mouse.position = (action.set.x, action.set.y)
    elif action.click:
        _logger.debug(
            "Click mouse %s",
            action.click.button,
        )
        mouse.click(
            getattr(Button, action.click.button),
            1,
        )
    elif action.release:
        _logger.debug("Release mouse %s", action.release.button)
        mouse.release(getattr(Button, action.release.button))
    elif action.press:
        _logger.debug("Press mouse %s", action.press.button)
        mouse.press(getattr(Button, action.press.button))


def _do_run_command(command) -> None:
    _logger.debug("Running command: %s", command)
    result = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
    )
    _logger.debug("Command output: %s", result.stdout)
    _logger.debug("Command error: %s", result.stderr)
    _logger.debug("Command return code: %s", result.returncode)


def command_action(command: str) -> None:  # pragma: no cover
    try:
        asyncio.create_task(asyncio.to_thread(_do_run_command, command))
    except Exception as e:
        _logger.error("Error running commands: %s", e)


def webhook_action(webhook: WebhookAction) -> None:
    try:
        result = _session.request(
            webhook.method,
            webhook.url,
            json=webhook.data,
            params=webhook.params,
            headers={str(key): str(value) for key, value in webhook.headers.items()},
        )
        _logger.info("Webhook result: %i %s", result.status_code, result.text)
    except Exception as e:
        _logger.warning("Webhook resulted in an exception %s", e)
