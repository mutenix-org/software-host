# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import logging
import os
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

import requests
from mutenix.config import ActionEnum
from mutenix.config import ButtonAction
from mutenix.config import LedStatusSource
from mutenix.config import load_config
from mutenix.config import save_config
from mutenix.hid_commands import LedColor
from mutenix.hid_commands import SetLed
from mutenix.hid_commands import Status
from mutenix.hid_commands import UpdateConfig
from mutenix.hid_commands import VersionInfo
from mutenix.hid_device import HidDevice
from mutenix.teams_messages import ClientMessage
from mutenix.teams_messages import ClientMessageParameter
from mutenix.teams_messages import MeetingAction
from mutenix.teams_messages import ServerMessage
from mutenix.updates import check_for_device_update
from mutenix.updates import perform_upgrade_with_file
from mutenix.utils import bring_teams_to_foreground
from mutenix.utils import run_loop
from mutenix.virtual_macropad import VirtualMacropad
from mutenix.websocket_client import Identifier
from mutenix.websocket_client import WebSocketClient

_logger = logging.getLogger(__name__)


class Macropad:
    """The main logic for the Macropad."""

    def __init__(self, config_file: Path | None = None):
        self._run = True
        self._version_seen = None
        self._last_status_check: defaultdict[int, int] = defaultdict(int)
        self._config = load_config(config_file)
        self._last_led_update: dict[int, SetLed] = {}
        self._setup()
        self._current_state: ServerMessage | None = None
        self._setup_buttons()
        self._checktime = time.time()

    def _setup(self):
        self._device = HidDevice(self._config.device_identifications)
        token = self._config.teams_token
        self._websocket = WebSocketClient(
            "ws://127.0.0.1:8124",
            Identifier(
                manufacturer="test",
                device="test",
                app="test",
                app_version="1.0.0",
                token=token,
            ),
        )
        self._virtual_macropad = VirtualMacropad(
            self._config.virtual_keypad.bind_address,
            self._config.virtual_keypad.bind_port,
        )
        self._websocket.register_callback(self._teams_callback)
        self._device.register_callback(self._hid_callback)
        self._virtual_macropad.register_callback(self._hid_callback)

    def _setup_buttons(self):
        self._tap_actions = {entry.button_id: entry for entry in self._config.actions}
        self._double_tap_actions = {
            entry.button_id: entry for entry in self._config.double_tap_action
        }

    async def _send_status(self, status: Status):
        _logger.debug("Status: %s", status)
        action: None | ButtonAction = None
        mapped_action: Callable | None | MeetingAction = None

        def perform_webhook(extra):
            requests.request(
                extra.get("method", "GET"),
                extra["url"],
                json=extra.get("data", None),
                headers={
                    str(key): str(value)
                    for key, value in extra.get("headers", {}).items()
                },
            )

        action_map: dict[ActionEnum, Callable] = {
            ActionEnum.ACTIVATE_TEAMS: bring_teams_to_foreground,
            ActionEnum.CMD: lambda extra: os.system(extra) if extra else None,
            ActionEnum.WEBHOOK: perform_webhook,
        }

        if status.triggered:
            if not status.released:
                return
            if not status.doubletap and status.button in self._tap_actions:
                action = self._tap_actions.get(status.button, None)
            elif status.doubletap and status.button in self._double_tap_actions:
                action = self._double_tap_actions.get(status.button, None)
            if not action:
                return
            if isinstance(action.action, MeetingAction):
                mapped_action = action.action
            else:
                mapped_action = action_map.get(action.action, None)
            if mapped_action:
                if callable(mapped_action):
                    if action.action in [ActionEnum.CMD, ActionEnum.WEBHOOK]:
                        mapped_action(action.extra)  # pragma: no cover
                    else:
                        mapped_action()
                else:
                    if action.action == MeetingAction.React:
                        client_message = ClientMessage.create(
                            action=MeetingAction.React,
                        )
                        client_message.parameters = ClientMessageParameter(
                            type_=action.extra,
                        )
                    else:
                        client_message = ClientMessage.create(action=mapped_action)
                    await self._websocket.send_message(client_message)

    async def _process_version_info(self, version_info: VersionInfo):
        if self._version_seen != version_info.version:
            _logger.info(version_info)
            self._version_seen = version_info.version
            if self._config.auto_update:
                check_for_device_update(self._device.raw, version_info)
        else:
            _logger.debug(version_info)
        await self._update_device_status(force=True)

    async def _hid_callback(self, msg):
        if isinstance(msg, Status):
            await self._send_status(msg)
        elif isinstance(msg, VersionInfo):
            await self._process_version_info(msg)

    async def _teams_callback(self, msg: ServerMessage):
        _logger.debug("Teams message: %s", msg)
        if msg.meeting_update:
            self._current_state = msg
        if msg.token_refresh:
            self._config.teams_token = msg.token_refresh
            save_config(self._config)
        await self._update_device_status()

    async def _update_device_status(self, force=False):
        msg = self._current_state
        msgs = {}

        def map_led_color(color):
            if not hasattr(LedColor, color.upper()):
                return LedColor.GREEN
            return getattr(LedColor, color.upper())

        for ledstatus in self._config.leds:
            if ledstatus.source == LedStatusSource.TEAMS:
                color = "black"
                if (
                    msg
                    and msg.meeting_update
                    and msg.meeting_update.meeting_state
                    and msg.meeting_update.meeting_state.is_in_meeting
                ):
                    mapped_state = getattr(
                        msg.meeting_update.meeting_state,
                        ledstatus.extra.replace("-", "_").lower(),
                    )
                    color = ledstatus.color_on if mapped_state else ledstatus.color_off
                    msgs[ledstatus.button_id] = SetLed(
                        ledstatus.button_id,
                        map_led_color(color),
                    )
                else:
                    msgs[ledstatus.button_id] = SetLed(
                        ledstatus.button_id,
                        map_led_color("black"),
                    )
            elif ledstatus.source == LedStatusSource.CMD:
                if (
                    self._last_status_check[ledstatus.button_id] + ledstatus.interval
                    > time.time()
                ):
                    continue
                if ledstatus.read_result:
                    result = await asyncio.to_thread(
                        subprocess.check_output,
                        ledstatus.extra,
                    )
                    msgs[ledstatus.button_id] = SetLed(
                        ledstatus.button_id,
                        map_led_color(result.strip()),
                    )
                else:
                    result = await asyncio.to_thread(
                        subprocess.check_call,
                        ledstatus.extra,
                    )
                    msgs[ledstatus.button_id] = SetLed(
                        ledstatus.button_id,
                        map_led_color(
                            ledstatus.color_on if result == 0 else ledstatus.color_off,
                        ),
                    )
                self._last_status_check[ledstatus.button_id] = time.time()

        for key, message in msgs.items():
            try:
                if not force and (
                    key in self._last_led_update
                    and self._last_led_update[key] == message
                ):
                    continue
                _logger.debug(
                    f"Sending message: {message}, prev: {self._last_led_update.get(key, None)}",
                )
                self._device.send_msg(message)
                await self._virtual_macropad.send_msg(message)
                self._last_led_update[key] = message
            except Exception as e:
                _logger.exception(e)

    async def _do_check_status(self):
        from mutenix.tray_icon import my_icon

        await self._update_device_status()
        await asyncio.sleep(0.1)
        if int(time.time() - self._checktime) > 10:
            try:
                if my_icon:
                    my_icon.update_menu()
                self._checktime = time.time()
            except Exception as e:
                _logger.error("Error updating tray icon: %s", e)
                print(e)

    _check_status = run_loop(_do_check_status)

    async def process(self):
        """Starts the process loop for the device and the WebSocket connection."""
        try:
            await asyncio.gather(
                self._device.process(),
                self._websocket.process(),
                self._virtual_macropad.process(),
                self._check_status(),
            )
        except Exception as e:
            _logger.error("Error in Macropad process: %s", e)

    async def manual_update(self, update_file):
        """Manually update the device with a given file."""
        await self._device.wait_for_device()
        with open(update_file, "rb") as f:
            perform_upgrade_with_file(self._device.raw, f)

    async def stop(self):
        """Stops the device and WebSocket connection."""
        self._run = False
        await self._device.stop()
        _logger.info("Device stopped")
        await self._websocket.stop()
        _logger.info("Websocket stopped")
        await self._virtual_macropad.stop()
        _logger.info("Virtual Device stopped")

    @property
    def virtual_keypad_address(self):
        return self._config.virtual_keypad.bind_address

    @property
    def virtual_keypad_port(self):
        return self._config.virtual_keypad.bind_port

    def activate_serial_console(self):
        message = UpdateConfig()
        message.activate_debug(True)
        self._device.send_msg(message)

    def deactivate_serial_console(self):
        message = UpdateConfig()
        message.activate_debug(False)
        self._device.send_msg(message)

    def activate_filesystem(self):
        message = UpdateConfig()
        message.activate_filesystem(True)
        self._device.send_msg(message)

    @property
    def teams_connected(self) -> bool:
        return self._websocket.connected

    @property
    def device_connected(self) -> bool:
        return self._device.connected
