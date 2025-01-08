from __future__ import annotations

import asyncio
import logging
import os
from typing import Callable

from mutenix.config import ActionEnum
from mutenix.config import ButtonAction
from mutenix.config import load_config
from mutenix.config import save_config
from mutenix.hid_commands import LedColor
from mutenix.hid_commands import SetLed
from mutenix.hid_commands import Status
from mutenix.hid_commands import VersionInfo
from mutenix.hid_device import HidDevice
from mutenix.teams_messages import ClientMessage
from mutenix.teams_messages import ClientMessageParameter
from mutenix.teams_messages import MeetingAction
from mutenix.teams_messages import ServerMessage
from mutenix.updates import check_for_device_update
from mutenix.updates import perform_upgrade_with_file
from mutenix.utils import bring_teams_to_foreground
from mutenix.virtual_macropad import VirtualMacropad
from mutenix.websocket_client import Identifier
from mutenix.websocket_client import WebSocketClient

_logger = logging.getLogger(__name__)


class Macropad:
    """The main logic for the Macropad."""

    def __init__(self, vid=0x2E8A, pid=0x2083):
        self._version_seen = None
        self._config = load_config()
        self._setup(vid, pid)
        self._current_state = None
        self._setup_buttons()

    def _setup(self, vid=0x2E8A, pid=0x2083):
        self._device = HidDevice(vid, pid)
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
        self._virtual_macropad = VirtualMacropad()
        self._websocket.register_callback(self._teams_callback)
        self._device.register_callback(self._hid_callback)
        self._virtual_macropad.register_callback(self._hid_callback)

    def _setup_buttons(self):
        self._tap_actions = {entry.button_id: entry for entry in self._config.actions}
        self._double_tap_actions = {entry.button_id: entry for entry in self._config.double_tap_action}

    async def _send_status(self, status: Status):
        _logger.debug("Status: %s", status)
        action: None | ButtonAction = None
        mapped_action: Callable | None | MeetingAction = None
        action_map: dict[ActionEnum, Callable] = {
            ActionEnum.ACTIVATE_TEAMS: bring_teams_to_foreground,
            ActionEnum.CMD: lambda extra: os.system(extra) if extra else None,
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
                    if action.action == ActionEnum.CMD:
                        mapped_action(action.extra)
                    else:
                        mapped_action()
                else:
                    if action.action == MeetingAction.React:
                        client_message = ClientMessage.create(action=MeetingAction.React)
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
            check_for_device_update(self._device.raw, version_info)
        else:
            _logger.debug(version_info)
        await self._update_device_status()

    async def _hid_callback(self, msg):
        if isinstance(msg, Status):
            await self._send_status(msg)
        elif isinstance(msg, VersionInfo):
            await self._process_version_info(msg)

    async def _teams_callback(self, msg: ServerMessage):
        _logger.debug("Teams message: %s", msg)
        self._current_state = msg
        if msg.token_refresh:
            self._config.teams_token = msg.token_refresh
            try:
                save_config(self._config)
            except IOError as e:
                _logger.error("Failed to write token to file: %s", e)
        await self._update_device_status()

    async def _update_device_status(self):
        if self._current_state is None:
            return
        msgs = {}
        msg = self._current_state

        def set_led(id, condition, true_color, false_color):
            if condition:
                msgs[id] = SetLed(id, true_color)
            else:
                msgs[id] = SetLed(id, false_color)

        if msg.meeting_update:
            if msg.meeting_update.meeting_state:
                state = msg.meeting_update.meeting_state
                if state.is_in_meeting:
                    set_led(1, state.is_muted, LedColor.RED, LedColor.GREEN)
                    set_led(
                        2, state.is_hand_raised,
                        LedColor.YELLOW, LedColor.WHITE,
                    )
                    set_led(3, state.is_video_on, LedColor.GREEN, LedColor.RED)
                else:
                    for i in range(1, 6):
                        set_led(i, False, LedColor.BLACK, LedColor.BLACK)

            if msg.meeting_update.meeting_permissions:
                permissions = msg.meeting_update.meeting_permissions
                set_led(
                    5, permissions.can_leave,
                    LedColor.GREEN, LedColor.BLACK,
                )

        for m in msgs.values():
            try:
                self._device.send_msg(m)
                await self._virtual_macropad.send_msg(m)
            except Exception as e:
                print(e)

    async def process(self):
        """Starts the process loop for the device and the WebSocket connection."""
        try:
            await asyncio.gather(
                self._device.process(),
                self._websocket.process(),
                self._virtual_macropad.process(),
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
        await self._device.stop()
        _logger.info("Device stopped")
        await self._websocket.stop()
        _logger.info("Websocket stopped")
        await self._virtual_macropad.stop()
        _logger.info("Virtual Device stopped")
