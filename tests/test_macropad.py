# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from unittest.mock import ANY
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import mock_open
from unittest.mock import patch

import pytest
from mutenix.macropad import Macropad
from mutenix.models.config import Config
from mutenix.models.config import LedColor as ConfigLedColor
from mutenix.models.config import TeamsState
from mutenix.models.hid_commands import LedColor
from mutenix.models.hid_commands import SetLed
from mutenix.models.hid_commands import Status
from mutenix.models.hid_commands import VersionInfo
from mutenix.models.teams_messages import ClientMessageParameter
from mutenix.models.teams_messages import ClientMessageParameterType
from mutenix.models.teams_messages import MeetingAction
from mutenix.models.teams_messages import MeetingPermissions
from mutenix.models.teams_messages import MeetingState
from mutenix.models.teams_messages import MeetingUpdate
from mutenix.models.teams_messages import ServerMessage

try:
    from pynput.keyboard import Key
    from pynput.mouse import Button
except ImportError:
    Key = Mock()
    Button = Mock()


patch("mutenix.actions.keyboard_action")
patch("mutenix.actions.mouse_action")
patch("mutenix.actions.command_action")
patch("mutenix.actions.webhook_action")


@pytest.fixture
def macropad():
    with (
        patch("mutenix.macropad.HidDevice") as MockHidDevice,
        patch("mutenix.macropad.TeamsWebSocketClient") as MockWebSocketClient,
        patch("mutenix.macropad.WebServer") as MockVirtualMacropad,
        patch("mutenix.config.save_config"),
    ):
        mock_device = Mock()
        mock_device.connected = True
        MockHidDevice.return_value = mock_device
        MockWebSocketClient.return_value = Mock()
        MockVirtualMacropad.return_value = Mock()
        return Macropad(Config())


@pytest.mark.asyncio
async def test_hid_callback_status(macropad):
    msg = Status(bytes([1, 1, 0, 0, 1]))
    macropad._teams_websocket.send_message = AsyncMock()
    await macropad._hid_callback(msg)
    macropad._teams_websocket.send_message.assert_called_once()
    assert (
        macropad._teams_websocket.send_message.call_args[0][0].action
        == MeetingAction.ToggleMute
    )


@pytest.mark.asyncio
async def test_hid_callback_version_info(macropad):
    msg = VersionInfo(bytes([1, 0, 0, 2]))
    macropad._version_seen = None
    with patch(
        "mutenix.macropad.check_for_device_update",
    ) as mock_check_for_device_update:
        await macropad._hid_callback(msg)
        mock_check_for_device_update.assert_called_once_with(ANY, msg, ANY)


@pytest.mark.asyncio
async def test_hid_callback_version_info_only_once(macropad):
    msg = VersionInfo(bytes([1, 0, 0, 2]))
    macropad._version_seen = None
    await macropad._hid_callback(msg)
    with patch(
        "mutenix.macropad.check_for_device_update",
    ) as mock_check_for_device_update:
        await macropad._hid_callback(msg)
        mock_check_for_device_update.assert_not_called()


@pytest.mark.asyncio
async def test_teams_callback_token_refresh(macropad):
    msg = ServerMessage(tokenRefresh="new_token")
    macropad._current_state = None
    with patch("pathlib.Path.open", mock_open()) as mock_file:
        await macropad._teams_callback(msg)
        mock_file.assert_called_once()
        assert str(mock_file.call_args[0][0]).endswith("w")
        mock_file().write.assert_any_call("new_token")


@pytest.mark.asyncio
async def test_teams_callback_token_refresh_save_failed(macropad):
    msg = ServerMessage(tokenRefresh="new_token")
    macropad._current_state = None
    with (
        patch("pathlib.Path.open", mock_open()) as mock_file,
        patch("mutenix.macropad._logger.error"),
    ):
        mock_file().write.side_effect = IOError
        await macropad._teams_callback(msg)
        mock_file.assert_called()
        assert str(mock_file.call_args[0][0]).endswith("w")


@pytest.mark.asyncio
async def test_update_device_status(macropad):
    macropad._current_state = ServerMessage(
        meetingUpdate=MeetingUpdate(
            meetingState=MeetingState(
                isInMeeting=True,
                isMuted=True,
                isHandRaised=False,
                isVideoOn=True,
            ),
            meetingPermissions=MeetingPermissions(canLeave=True),
        ),
    )

    def send_msg(msg):
        future = asyncio.get_event_loop().create_future()
        future.set_result(None)
        assert isinstance(msg, SetLed)
        return future

    macropad._device.send_msg = Mock(side_effect=send_msg)
    macropad._virtual_macropad.send_msg = AsyncMock()
    await macropad._update_device_status()
    assert macropad._device.send_msg.call_count == 8
    assert macropad._virtual_macropad.send_msg.call_count == 8


@pytest.mark.asyncio
async def test_update_device_status_not_in_meeting(macropad):
    macropad._current_state = ServerMessage(
        meetingUpdate=MeetingUpdate(
            meetingState=MeetingState(
                isInMeeting=False,
                isMuted=False,
                isHandRaised=False,
                isVideoOn=False,
            ),
            meetingPermissions=MeetingPermissions(canLeave=False),
        ),
    )

    def send_msg(msg):
        future = asyncio.get_event_loop().create_future()
        future.set_result(None)
        assert isinstance(msg, SetLed)
        return future

    macropad._device.send_msg = Mock(side_effect=send_msg)
    macropad._virtual_macropad.send_msg = AsyncMock()
    await macropad._update_device_status()
    assert macropad._device.send_msg.call_count == 8
    assert macropad._virtual_macropad.send_msg.call_count == 8


@pytest.mark.parametrize(
    "msg_bytes, expected_action, should_call",
    [
        (bytes([1, 1, 0, 0, 1]), MeetingAction.ToggleMute, True),
        (bytes([2, 1, 0, 0, 1]), MeetingAction.ToggleHand, True),
        (bytes([4, 1, 0, 0, 1]), MeetingAction.React, True),
        (bytes([5, 1, 0, 0, 1]), MeetingAction.LeaveCall, True),
        (bytes([1, 0, 0, 0, 1]), None, False),
        (bytes([2, 0, 0, 0, 1]), None, False),
        (bytes([4, 0, 0, 0, 1]), None, False),
        (bytes([5, 0, 0, 0, 1]), None, False),
        (bytes([1, 1, 0, 0, 0]), None, False),
        (bytes([2, 1, 0, 0, 0]), None, False),
        (bytes([4, 1, 0, 0, 0]), None, False),
        (bytes([5, 1, 0, 0, 0]), None, False),
    ],
)
@pytest.mark.asyncio
async def test_hid_callback_parametrized(
    macropad,
    msg_bytes,
    expected_action: MeetingAction,
    should_call,
):
    msg = Status(msg_bytes)
    macropad._teams_websocket.send_message = AsyncMock()

    await macropad._hid_callback(msg)
    if should_call:
        macropad._teams_websocket.send_message.assert_called_once()
        if expected_action:
            assert (
                macropad._teams_websocket.send_message.call_args[0][0].action.name
                == expected_action.name
            )
    else:
        macropad._teams_websocket.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_hid_callback_invalid_button(macropad):
    msg = Status([11, 1, 0, 0, 1])

    await macropad._hid_callback(msg)
    macropad._teams_websocket.send_message.assert_not_called()


class IdentifierWithoutToken:
    def __eq__(self, value):
        if value.token:
            return False
        return True


@pytest.mark.asyncio
async def test_setup_without_existing_token():
    with patch("builtins.open", mock_open(read_data="")) as mock_file:
        mock_file.side_effect = FileNotFoundError
        with (
            patch("mutenix.macropad.HidDevice"),
            patch("mutenix.macropad.TeamsWebSocketClient") as MockWebSocketClient,
            patch("mutenix.macropad.WebServer"),
        ):
            macropad = Macropad(Config())
            macropad._setup()
            MockWebSocketClient.assert_called_with(
                ANY,
                ANY,
                IdentifierWithoutToken(),
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, expected_action, expected_parameters",
    [
        (Status(bytes([1, 1, 0, 0, 1])), MeetingAction.ToggleMute, None),
        (Status(bytes([2, 1, 0, 0, 1])), MeetingAction.ToggleHand, None),
        # bring_teams_to_foreground
        (Status(bytes([3, 1, 0, 0, 1])), None, None),
        (
            Status(bytes([3, 1, 1, 0, 1])),
            MeetingAction.ToggleVideo,
            None,
        ),  # longpressed
        (
            Status(bytes([4, 1, 0, 0, 1])),
            MeetingAction.React,
            ClientMessageParameter(type_=ClientMessageParameterType.ReactLike),
        ),
        (Status(bytes([5, 1, 0, 0, 1])), MeetingAction.LeaveCall, None),
        (Status(bytes([1, 0, 0, 0, 1])), None, None),
    ],
)
async def test_send_status(macropad, status, expected_action, expected_parameters):
    macropad._teams_websocket.send_message = AsyncMock()
    with patch(
        "mutenix.macropad.bring_teams_to_foreground",
    ) as mock_bring_teams_to_foreground:
        await macropad._send_status(status)
        if expected_action:
            macropad._teams_websocket.send_message.assert_called_once()
            client_message = macropad._teams_websocket.send_message.call_args[0][0]
            assert client_message.action == expected_action
            if expected_parameters:
                assert client_message.parameters == expected_parameters
        else:
            macropad._teams_websocket.send_message.assert_not_called()
            if status.button == 3 and status.triggered and status.released:
                mock_bring_teams_to_foreground.assert_called_once()
            else:
                mock_bring_teams_to_foreground.assert_not_called()


@pytest.mark.asyncio
async def test_process(macropad):
    macropad._device.process = AsyncMock()
    macropad._teams_websocket.process = AsyncMock()
    macropad._virtual_macropad.process = AsyncMock()

    async def stop_macropad():
        await asyncio.sleep(0.2)
        await macropad.stop()

    asyncio.create_task(stop_macropad())

    await macropad.process()

    macropad._device.process.assert_called_once()
    macropad._teams_websocket.process.assert_called_once()
    macropad._virtual_macropad.process.assert_called_once()


@pytest.mark.asyncio
async def test_process_with_exception(macropad):
    macropad._device.process = AsyncMock(side_effect=Exception("Device error"))
    macropad._teams_websocket.process = AsyncMock(return_value=None)
    macropad._virtual_macropad.process = AsyncMock(return_value=None)

    macropad._check_status = AsyncMock()

    with patch("mutenix.macropad._logger.error") as mock_logger_error:
        await macropad.process()
        mock_logger_error.assert_called_with("Error in Macropad process: %s", ANY)

    macropad._device.process.assert_called_once()
    macropad._teams_websocket.process.assert_called_once()
    macropad._virtual_macropad.process.assert_called_once()


@pytest.mark.asyncio
async def test_manual_update_success(macropad):
    update_file = "update.bin"
    macropad._device.wait_for_device = AsyncMock()
    with patch("builtins.open", mock_open(read_data=b"update_data")) as mock_file:
        with patch(
            "mutenix.macropad.perform_upgrade_with_file",
        ) as mock_perform_upgrade:
            await macropad.manual_update(update_file)
            macropad._device.wait_for_device.assert_called_once()
            mock_file.assert_called_once_with(update_file, "rb")
            mock_perform_upgrade.assert_called_once_with(
                macropad._device.raw,
                mock_file(),
            )


@pytest.mark.asyncio
async def test_manual_update_file_not_found(macropad):
    update_file = "non_existent_update.bin"
    macropad._device.wait_for_device = AsyncMock()
    with patch("builtins.open", mock_open()) as mock_file:
        mock_file.side_effect = FileNotFoundError
        with patch(
            "mutenix.macropad.perform_upgrade_with_file",
        ) as mock_perform_upgrade:
            with pytest.raises(FileNotFoundError):
                await macropad.manual_update(update_file)
            macropad._device.wait_for_device.assert_called_once()
            mock_file.assert_called_once_with(update_file, "rb")
            mock_perform_upgrade.assert_not_called()


@pytest.mark.asyncio
async def test_manual_update_io_error(macropad):
    update_file = "update.bin"
    macropad._device.wait_for_device = AsyncMock()
    with patch("builtins.open", mock_open()) as mock_file:
        mock_file.side_effect = IOError
        with patch(
            "mutenix.macropad.perform_upgrade_with_file",
        ) as mock_perform_upgrade:
            with pytest.raises(IOError):
                await macropad.manual_update(update_file)
            macropad._device.wait_for_device.assert_called_once()
            mock_file.assert_called_once_with(update_file, "rb")
            mock_perform_upgrade.assert_not_called()


@pytest.mark.asyncio
async def test_stop():
    macropad = Macropad(Config())
    macropad._device = AsyncMock()
    macropad._teams_websocket = AsyncMock()
    macropad._virtual_macropad = AsyncMock()

    await macropad.stop()

    macropad._device.stop.assert_called_once()
    macropad._teams_websocket.stop.assert_called_once()
    macropad._virtual_macropad.stop.assert_called_once()


@pytest.mark.asyncio
async def test_update_device_status_teams_source_in_meeting(macropad):
    macropad._config.leds = [
        Mock(
            button_id=1,
            teams_state=Mock(
                teams_state=TeamsState.MUTED,
                color_on=ConfigLedColor.RED,
                color_off=ConfigLedColor.GREEN,
            ),
        ),
    ]
    macropad._current_state = ServerMessage(
        meetingUpdate=MeetingUpdate(
            meetingState=MeetingState(
                isInMeeting=True,
                isMuted=True,
                isHandRaised=False,
                isVideoOn=True,
            ),
            meetingPermissions=MeetingPermissions(canLeave=True),
        ),
    )

    macropad._device.send_msg = Mock()
    macropad._virtual_macropad.send_msg = AsyncMock()

    await macropad._update_device_status()

    macropad._device.send_msg.assert_called_once_with(SetLed(1, LedColor.RED))
    macropad._virtual_macropad.send_msg.assert_called_once_with(SetLed(1, LedColor.RED))


@pytest.mark.asyncio
async def test_update_device_status_teams_source_not_in_meeting(macropad):
    macropad._config.leds = [
        Mock(
            button_id=1,
            teams_state=Mock(
                teams_state=TeamsState.MUTED,
                color_on=ConfigLedColor.RED,
                color_off=ConfigLedColor.GREEN,
            ),
        ),
    ]
    macropad._current_state = ServerMessage(
        meetingUpdate=MeetingUpdate(
            meetingState=MeetingState(
                isInMeeting=False,
                isMuted=False,
                isHandRaised=False,
                isVideoOn=False,
            ),
            meetingPermissions=MeetingPermissions(canLeave=False),
        ),
    )

    macropad._device.send_msg = Mock()
    macropad._virtual_macropad.send_msg = AsyncMock()

    await macropad._update_device_status()

    macropad._device.send_msg.assert_called_once_with(SetLed(1, LedColor.BLACK))
    macropad._virtual_macropad.send_msg.assert_called_once_with(
        SetLed(1, LedColor.BLACK),
    )


@pytest.mark.asyncio
async def test_update_device_status_cmd_source_with_result(macropad):
    macropad._config.leds = [
        Mock(
            button_id=1,
            teams_state=False,
            result_command=False,
            color_command=Mock(
                command="echo blue",
                interval=0,
                timeout=1.0,
            ),
        ),
    ]
    macropad._last_status_check = defaultdict(int)
    macropad._device.send_msg = Mock()
    macropad._virtual_macropad.send_msg = AsyncMock()

    with patch("asyncio.to_thread", return_value=b"blue"):
        await macropad._update_device_status()

    macropad._device.send_msg.assert_called_once_with(SetLed(1, LedColor.BLUE))
    macropad._virtual_macropad.send_msg.assert_called_once_with(
        SetLed(1, LedColor.BLUE),
    )


@pytest.mark.asyncio
async def test_update_device_status_cmd_source_without_result(macropad):
    macropad._config.leds = [
        Mock(
            button_id=1,
            teams_state=False,
            result_command=Mock(
                command="exit 0",
                interval=0,
                read_result=False,
                color_on=ConfigLedColor.YELLOW,
                color_off=ConfigLedColor.BLACK,
                timeout=1.0,
            ),
        ),
    ]
    macropad._last_status_check = defaultdict(int)
    macropad._device.send_msg = Mock()
    macropad._virtual_macropad.send_msg = AsyncMock()

    with patch("asyncio.to_thread", return_value=0):
        await macropad._update_device_status()

    macropad._device.send_msg.assert_called_once_with(SetLed(1, LedColor.YELLOW))
    macropad._virtual_macropad.send_msg.assert_called_once_with(
        SetLed(1, LedColor.YELLOW),
    )


@pytest.mark.asyncio
async def test_update_device_status_cmd_source_interval_not_elapsed(macropad):
    macropad._config.leds = [
        Mock(
            button_id=1,
            teams_state=False,
            result_command=Mock(
                command="exit 0",
                interval=10,
                read_result=False,
                color_on=ConfigLedColor.YELLOW,
                color_off=ConfigLedColor.BLACK,
                timeout=1.0,
            ),
        ),
    ]
    macropad._last_status_check = defaultdict(lambda: time.time())
    macropad._device.send_msg = AsyncMock()
    macropad._virtual_macropad.send_msg = AsyncMock()

    await macropad._update_device_status()

    macropad._device.send_msg.assert_not_called()
    macropad._virtual_macropad.send_msg.assert_not_called()


@pytest.mark.asyncio
async def test_do_check_status_update_device_status_called(macropad):
    macropad._update_device_status = AsyncMock()
    macropad._checktime = time.time() - 11  # Ensure the time condition is met

    await macropad._do_check_status()

    macropad._update_device_status.assert_called_once()


@pytest.mark.asyncio
async def test_do_check_status_sleep_called(macropad):
    macropad._update_device_status = AsyncMock()
    macropad._checktime = time.time() - 11  # Ensure the time condition is met

    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        await macropad._do_check_status()
        mock_sleep.assert_called_once_with(0.1)


def test_activate_serial_console(macropad):
    macropad._device.send_msg = Mock()
    macropad.activate_serial_console()
    macropad._device.send_msg.assert_called_once()
    sent_message = macropad._device.send_msg.call_args[0][0]
    assert sent_message._activate_debug == 2
    assert sent_message._activate_filesystem == 0


def test_deactivate_serial_console(macropad):
    macropad._device.send_msg = Mock()
    macropad.deactivate_serial_console()
    macropad._device.send_msg.assert_called_once()
    sent_message = macropad._device.send_msg.call_args[0][0]
    assert sent_message._activate_debug == 1
    assert sent_message._activate_filesystem == 0


def test_activate_filesystem(macropad):
    macropad._device.send_msg = Mock()
    macropad.activate_filesystem()
    macropad._device.send_msg.assert_called_once()
    sent_message = macropad._device.send_msg.call_args[0][0]
    assert sent_message._activate_filesystem == 2


@pytest.mark.asyncio
async def test_reload_config(macropad):
    with (
        patch("mutenix.macropad.load_config") as mock_load_config,
        patch("mutenix.macropad._logger.info") as mock_logger_info,
        patch.object(macropad, "_setup_buttons") as mock_setup_buttons,
        patch.object(macropad, "_update_device_status") as mock_update_device_status,
    ):
        mock_load_config.return_value = Config()
        await macropad._reload_config_async()
        mock_load_config.assert_called_once()
        mock_setup_buttons.assert_called_once()
        mock_update_device_status.assert_called_once_with(force=True)
        mock_logger_info.assert_any_call("Reloading config")
        mock_logger_info.assert_any_call("Config reloaded")


@pytest.mark.asyncio
async def test_teams_callback_meeting_update(macropad):
    msg = ServerMessage(
        meetingUpdate=MeetingUpdate(
            meetingState=MeetingState(
                isInMeeting=True,
                isMuted=False,
                isHandRaised=False,
                isVideoOn=True,
            ),
            meetingPermissions=MeetingPermissions(canLeave=True),
        ),
    )
    macropad._current_state = None
    await macropad._teams_callback(msg)
    assert macropad._current_state == msg


@pytest.mark.asyncio
async def test_teams_callback_update_device_status_called(macropad):
    msg = ServerMessage(
        meetingUpdate=MeetingUpdate(
            meetingState=MeetingState(
                isInMeeting=True,
                isMuted=False,
                isHandRaised=False,
                isVideoOn=True,
            ),
            meetingPermissions=MeetingPermissions(canLeave=True),
        ),
    )
    macropad._current_state = None
    with patch.object(macropad, "_update_device_status") as mock_update_device_status:
        await macropad._teams_callback(msg)
        mock_update_device_status.assert_called_once()


@pytest.mark.asyncio
async def test_update_device_status_webhook_source_with_color(macropad):
    macropad._config.leds = [
        Mock(
            button_id=1,
            teams_state=False,
            result_command=False,
            color_command=False,
            webhook=True,
        ),
    ]
    macropad._state.led_colors[1] = "red"
    macropad._device.send_msg = Mock()
    macropad._virtual_macropad.send_msg = AsyncMock()

    await macropad._update_device_status()

    macropad._device.send_msg.assert_called_once_with(SetLed(1, LedColor.RED))
    macropad._virtual_macropad.send_msg.assert_called_once_with(SetLed(1, LedColor.RED))


@pytest.mark.asyncio
async def test_update_device_status_webhook_source_with_invalid_color(macropad):
    macropad._config.leds = [
        Mock(
            button_id=1,
            teams_state=False,
            result_command=False,
            color_command=False,
            webhook=True,
        ),
    ]
    macropad._virtual_macropad.get_led_status = Mock(return_value="invalid_color")
    macropad._device.send_msg = Mock()
    macropad._virtual_macropad.send_msg = AsyncMock()

    await macropad._update_device_status()

    macropad._device.send_msg.assert_called_once_with(SetLed(1, LedColor.BLACK))
    macropad._virtual_macropad.send_msg.assert_called_once_with(
        SetLed(1, LedColor.BLACK),
    )
