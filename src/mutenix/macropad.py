# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import logging
import shlex
import subprocess
import time
from collections import defaultdict

import requests
from mutenix.actions import command_action
from mutenix.actions import keyboard_action
from mutenix.actions import mouse_action
from mutenix.actions import webhook_action
from mutenix.config import load_config
from mutenix.config import save_config
from mutenix.hid_device import HidDevice
from mutenix.models.config import ActionDetails
from mutenix.models.config import ButtonAction
from mutenix.models.config import Config
from mutenix.models.config import LedColor as ConfigLedColor
from mutenix.models.config import LedStatus
from mutenix.models.config import WebhookAction
from mutenix.models.hid_commands import LedColor
from mutenix.models.hid_commands import SetLed
from mutenix.models.hid_commands import Status
from mutenix.models.hid_commands import UpdateConfig
from mutenix.models.hid_commands import VersionInfo
from mutenix.models.state import State
from mutenix.models.teams_messages import ClientMessage
from mutenix.models.teams_messages import ClientMessageParameter
from mutenix.models.teams_messages import MeetingAction
from mutenix.models.teams_messages import ServerMessage
from mutenix.updates import check_for_device_update
from mutenix.updates import perform_upgrade_with_file
from mutenix.utils import bring_teams_to_foreground
from mutenix.utils import run_loop
from mutenix.webserver import WebServer
from mutenix.websocket_client import Identifier
from mutenix.websocket_client import TeamsWebSocketClient

_logger = logging.getLogger(__name__)


class Macropad:
    """The main logic for the Macropad."""

    def __init__(self, config: Config):
        self._state = State()
        self._run = True
        self._version_seen = None
        self._last_status_check: defaultdict[int, float] = defaultdict(time.time)
        self._config = config
        self._last_led_update: dict[int, SetLed] = {}
        self._session = requests.Session()
        self._setup()
        self._current_state: ServerMessage | None = None
        self._setup_buttons()
        self._checktime = time.time()
        self._trigger_reload_config = False
        self._trigger_stop = False

    def _setup(self):
        self._state.config = self._config
        self._setup_device()
        self._setup_websocket()
        self._setup_virtual_macropad()

    def _setup_device(self):
        self._device = HidDevice(
            self._state.hardware,
            self._config.device_identifications,
        )
        self._device.register_callback(self._hid_callback)

    def _setup_websocket(self):
        token = self._config.teams_token
        self._teams_websocket = TeamsWebSocketClient(
            self._state.teams,
            "ws://127.0.0.1:8124",
            Identifier(
                manufacturer="test",
                device="test",
                app="test",
                app_version="1.0.0",
                token=token,
            ),
        )
        self._teams_websocket.register_callback(self._teams_callback)

    def _setup_virtual_macropad(self):
        self._virtual_macropad = WebServer(self._state, self._config.virtual_keypad)
        self._virtual_macropad.register_callback(self._hid_callback)

    def _setup_buttons(self):
        self._tap_actions = {entry.button_id: entry for entry in self._config.actions}
        self._longpress_actions = {
            entry.button_id: entry for entry in self._config.longpress_action
        }

    def _perform_webhook(self, extra: WebhookAction):
        try:
            result = self._session.request(
                extra.method,
                extra.url,
                json=extra.data,
                headers={str(key): str(value) for key, value in extra.headers.items()},
            )
            _logger.info("Webhook result: %i %s", result.status_code, result.text)
        except Exception as e:
            _logger.warning("Webhook resulted in an exception %s", e)

    async def _send_status(self, status: Status):
        _logger.info(
            "Button %s, Triggered: %s, Longpress: %s",
            status.button,
            status.triggered,
            status.longpressed,
        )
        _logger.debug("Status: %s", status)
        action: None | ButtonAction = None

        if status.triggered:
            if not status.released:
                return
            action = self._get_action(status)
            if not action:
                return

            await asyncio.create_task(self._execute_actions(action.actions))

    async def _execute_actions(self, actions: list[ActionDetails]):
        for single_action in actions:
            await self._execute_action(single_action)

    def _get_action(self, status):
        if not status.longpressed and status.button in self._tap_actions:
            return self._tap_actions.get(status.button, None)
        elif status.longpressed and status.button in self._longpress_actions:
            return self._longpress_actions.get(status.button, None)
        return None

    async def _execute_action(self, single_action: ActionDetails):
        if single_action.meeting_action:
            client_message = ClientMessage.create(
                action=single_action.meeting_action,
            )
            await self._teams_websocket.send_message(client_message)
        elif single_action.teams_reaction:
            client_message = ClientMessage.create(
                action=MeetingAction.React,
            )
            client_message.parameters = ClientMessageParameter(
                type_=single_action.teams_reaction.reaction,
            )
            await self._teams_websocket.send_message(client_message)
        elif single_action.activate_teams:
            bring_teams_to_foreground()
        elif single_action.command:
            command_action(single_action.command)
        elif single_action.webhook:
            webhook_action(single_action.webhook)
        elif single_action.keypress:
            keyboard_action(single_action.keypress)
        elif single_action.mouse:
            mouse_action(single_action.mouse)
        elif single_action.delay:
            await asyncio.sleep(single_action.delay)

    async def _process_version_info(self, version_info: VersionInfo):
        if self._version_seen != version_info.version:
            _logger.info(version_info)
            self._version_seen = version_info.version
            if self._config.auto_update:
                if check_for_device_update(
                    self._device.raw,
                    version_info,
                    self._config.proxy,
                ):
                    self._setup_device()
        else:
            _logger.debug(version_info)
        self._state.hardware.variant = version_info.type.name
        self._state.hardware.version = version_info.version
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

    def _map_led_color(self, color: ConfigLedColor):
        return getattr(LedColor, color.name, LedColor.GREEN)

    def _is_command_allowed_now(self, button_id, cmd_cfg):
        if self._last_status_check[button_id] + cmd_cfg.interval > time.time():
            return False
        _logger.debug(
            "Command to update led %d is allowed to run: %s",
            button_id,
            cmd_cfg,
        )
        return True

    async def _update_led(self, ledstatus: LedStatus):
        msg = self._current_state
        color: ConfigLedColor | None = ConfigLedColor.BLACK
        if ledstatus.teams_state:
            color = self._get_teams_state_color(ledstatus, msg)
        elif ledstatus.result_command:
            color = await self._get_result_command_color(ledstatus)
        elif ledstatus.color_command:
            color = await self._get_color_command_color(ledstatus)
        elif ledstatus.webhook:
            color = self._get_webhook_color(ledstatus)

        if color is None:
            return

        await self._send_led_message(
            ledstatus.button_id,
            SetLed(
                ledstatus.button_id,
                self._map_led_color(color),
            ),
        )

    def _get_teams_state_color(self, ledstatus, msg):
        if (
            msg
            and msg.meeting_update
            and msg.meeting_update.meeting_state
            and msg.meeting_update.meeting_state.is_in_meeting
        ):
            mapped_state = getattr(
                msg.meeting_update.meeting_state,
                ledstatus.teams_state.teams_state.value.replace("-", "_").lower(),
            )
            return (
                ledstatus.teams_state.color_on
                if mapped_state
                else ledstatus.teams_state.color_off
            )
        return ConfigLedColor.BLACK

    async def _get_result_command_color(self, ledstatus):
        cmd_cfg = ledstatus.result_command
        if not self._is_command_allowed_now(ledstatus.button_id, cmd_cfg):
            return None

        try:
            command = shlex.split(cmd_cfg.command)
            async with asyncio.timeout(cmd_cfg.timeout):
                exit_code: int = await asyncio.to_thread(
                    subprocess.check_call,
                    command,
                )
                color = cmd_cfg.color_on if exit_code == 0 else cmd_cfg.color_off
                _logger.debug(
                    "Result for %d: %d -> %s",
                    ledstatus.button_id,
                    exit_code,
                    color,
                )
                return color
        except Exception as e:
            _logger.warning("Error running command: %s %s", cmd_cfg, e)
            return ConfigLedColor.BLACK

    async def _get_color_command_color(self, ledstatus):
        cmd_cfg = ledstatus.color_command
        if not self._is_command_allowed_now(ledstatus.button_id, cmd_cfg):
            return None
        try:
            command = shlex.split(cmd_cfg.command)
            async with asyncio.timeout(cmd_cfg.timeout):
                result: bytes = await asyncio.to_thread(
                    subprocess.check_output,
                    command,
                )
                result_str = result.decode("utf-8")
                _logger.debug("Result for %d: %s", ledstatus.button_id, result_str)
                try:
                    return getattr(ConfigLedColor, result_str.strip().upper())
                except AttributeError:
                    _logger.warning("Unknown color: %s", result)
                    return ConfigLedColor.BLACK
        except Exception as e:
            _logger.warning("Error running command: %s %s", cmd_cfg, e)
            return ConfigLedColor.BLACK

    def _get_webhook_color(self, ledstatus):
        color_name = self._virtual_macropad.get_led_status(ledstatus.button_id)
        try:
            return ConfigLedColor[color_name.upper()]
        except KeyError:
            _logger.warning("Unknown color: %s", color_name)
            return ConfigLedColor.BLACK

    async def _send_led_message(self, key, message, force=False):
        try:
            if not force and (
                key in self._last_led_update and self._last_led_update[key] == message
            ):
                return
            _logger.debug(
                f"Sending message: {message}, prev: {self._last_led_update.get(key, None)}",
            )
            if self._device.connected:
                self._device.send_msg(message)
            await self._virtual_macropad.send_msg(message)
            self._last_led_update[key] = message
        except Exception as e:
            _logger.error("Error sending LED message: %s", e)

    async def _update_device_status(self, force=False):
        led_update_work = [
            self._update_led(ledstatus) for ledstatus in self._config.leds
        ]
        await asyncio.gather(*led_update_work)

    async def _do_check_status(self):
        from mutenix.tray_icon import my_icon

        await self._update_device_status()
        await asyncio.sleep(0.1)
        if int(time.time() - self._checktime) > 10:
            try:
                if my_icon:  # pragma: no cover
                    my_icon.update_menu()
                self._checktime = time.time()
            except Exception as e:  # pragma: no cover
                _logger.error("Error updating tray icon: %s", e)
        if self._trigger_reload_config:
            await self._reload_config_async()
            self._trigger_reload_config = False
        if self._trigger_stop:
            await self.stop()
            self._trigger_stop = False

    _check_status = run_loop(_do_check_status)

    async def process(self):
        """Starts the process loop for the device and the WebSocket connection."""
        try:
            await asyncio.gather(
                self._device.process(),
                self._teams_websocket.process(),
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
        await self._teams_websocket.stop()
        _logger.info("Websocket stopped")
        await self._virtual_macropad.stop()
        _logger.info("Virtual Device stopped")

    def trigger_stop(self):
        self._trigger_stop = True

    @property
    def virtual_keypad_address(self):  # pragma: no cover
        return self._config.virtual_keypad.bind_address

    @property
    def virtual_keypad_port(self):  # pragma: no cover
        return self._config.virtual_keypad.bind_port

    def activate_serial_console(self):
        message = UpdateConfig()
        message.activate_serial_console(True)
        self._device.send_msg(message)

    def deactivate_serial_console(self):
        message = UpdateConfig()
        message.activate_serial_console(False)
        self._device.send_msg(message)

    def activate_filesystem(self):
        message = UpdateConfig()
        message.activate_filesystem(True)
        self._device.send_msg(message)

    @property
    def teams_connected(self) -> bool:  # pragma: no cover
        return self._teams_websocket.connected

    @property
    def device_connected(self) -> bool:  # pragma: no cover
        return self._device.connected

    def reload_config(self):
        self._trigger_reload_config = True

    async def _reload_config_async(self):
        _logger.info("Reloading config")
        self._config = await asyncio.to_thread(load_config)
        self._setup_buttons()
        await self._update_device_status(force=True)
        self._virtual_macropad.set_config(self._config)
        self._state.config = self._config
        _logger.info("Config reloaded")

    @property
    def state(self):
        return self._state
