import asyncio
import logging

from mutenix.virtual_macropad import VirtualMacropad
from mutenix.utils import bring_teams_to_foreground
from mutenix.hid_device import HidDevice
from mutenix.websocket_client import WebSocketClient, Identifier
from mutenix.updates import check_for_device_update


from mutenix.hid_commands import (
    Status,
    VersionInfo,
    LedColor,
    SetLed,
)

from mutenix.teams_messages import (
    ServerMessage,
    ClientMessageParameterType,
    ClientMessageParameter,
    MeetingAction,
    ClientMessage,
)

# endregion

_logger = logging.getLogger(__name__)


class Macropad:
    """The main logic for the Macropad."""

    def __init__(self, vid=0x2E8A, pid=0x2083):
        self._version_seen = None
        self._setup(vid, pid)
        self._current_state = None

    def _setup(self, vid=0x2E8A, pid=0x2083):
        self._device = HidDevice(vid, pid)
        try:
            with open("macropad-teams-token.txt", "r") as f:
                token = f.read()
        except FileNotFoundError:
            token = ""
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

    async def _hid_callback(self, msg):
        if isinstance(msg, Status):
            _logger.debug(f"Status: {msg}")
            action = None
            if msg.button == 1 and msg.triggered and msg.released:
                action = MeetingAction.ToggleMute
            elif msg.button == 2 and msg.triggered and msg.released:
                action = MeetingAction.ToggleHand
            elif msg.button == 3 and msg.triggered and msg.released:
                if msg.doubletap:
                    action = MeetingAction.ToggleVideo
                else:
                    bring_teams_to_foreground()
            elif msg.button == 4 and msg.triggered and msg.released:
                action = MeetingAction.React
                parameters = ClientMessageParameter(
                    type_=ClientMessageParameterType.ReactLike
                )
            elif msg.button == 5 and msg.triggered and msg.released:
                action = MeetingAction.LeaveCall
            else:
                return

            if action is not None:
                client_message = ClientMessage.create(action=action)
                if msg.button == 4:
                    client_message.parameters = parameters

                await self._websocket.send_message(client_message)
        elif isinstance(msg, VersionInfo):
            if self._version_seen != msg.version:
                _logger.info(msg)
                self._version_seen = msg.version
                check_for_device_update(self._device, msg)
            else:
                _logger.debug(msg)
            await self._update_device_status()

    async def _teams_callback(self, msg: ServerMessage):
        _logger.debug("Teams message: %s", msg)
        self._current_state = msg
        if msg.token_refresh:
            try:
                with open("macropad-teams-token.txt", "w") as f:
                    f.write(msg.token_refresh)
            except IOError as e:
                _logger.error(f"Failed to write token to file: {e}")
        await self._update_device_status()

    async def _update_device_status(self):
        if self._current_state is None:
            return
        msgs = []
        msg = self._current_state

        def set_led(id, condition, true_color, false_color):
            if condition:
                msgs.append(SetLed(id, true_color))
            else:
                msgs.append(SetLed(id, false_color))

        if msg.meeting_update:
            if msg.meeting_update.meeting_state:
                state = msg.meeting_update.meeting_state
                if state.is_in_meeting:
                    set_led(1, state.is_muted, LedColor.RED, LedColor.GREEN)
                    set_led(2, state.is_hand_raised, LedColor.YELLOW, LedColor.WHITE)
                    set_led(3, state.is_video_on, LedColor.GREEN, LedColor.RED)
                else:
                    for i in range(5):
                        set_led(i, False, LedColor.BLACK, LedColor.BLACK)

            if msg.meeting_update.meeting_permissions:
                permissions = msg.meeting_update.meeting_permissions
                set_led(5, permissions.can_leave, LedColor.GREEN, LedColor.BLACK)

        for m in msgs:
            try:
                self._device.send_msg(m).add_done_callback(
                    lambda x: _logger.debug(f"Sent {x} bytes to device")
                )
                await self._virtual_macropad.send_msg(m).add_done_callback(
                    lambda x: _logger.debug(f"Sent {x} bytes to virtual device")
                )
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
            _logger.error(f"Error in Macropad process: {e}")