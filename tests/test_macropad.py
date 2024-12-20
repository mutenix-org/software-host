import pytest
import asyncio
from unittest.mock import ANY, AsyncMock, Mock, patch, mock_open
from mutenix.macropad import Macropad
from mutenix.hid_commands import SetLed, Status, VersionInfo
from mutenix.teams_messages import MeetingAction, MeetingPermissions, MeetingState, MeetingUpdate, ServerMessage

@pytest.fixture
def macropad():
    with patch("mutenix.macropad.HidDevice") as MockHidDevice, \
         patch("mutenix.macropad.WebSocketClient") as MockWebSocketClient, \
         patch("mutenix.macropad.VirtualMacropad") as MockVirtualMacropad:
        MockHidDevice.return_value = Mock()
        MockWebSocketClient.return_value = Mock()
        MockVirtualMacropad.return_value = Mock()
        return Macropad()

@pytest.mark.asyncio
async def test_hid_callback_status(macropad):
    msg = Status(bytes([1, 1, 0, 0, 1]))
    macropad._websocket.send_message = AsyncMock()
    await macropad._hid_callback(msg)
    macropad._websocket.send_message.assert_called_once()
    assert macropad._websocket.send_message.call_args[0][0].action == MeetingAction.ToggleMute

@pytest.mark.asyncio
async def test_hid_callback_version_info(macropad):
    msg = VersionInfo(bytes([1, 0, 0, 2]))
    macropad._version_seen = None
    with patch("mutenix.macropad.check_for_device_update") as mock_check_for_device_update:
        await macropad._hid_callback(msg)
        mock_check_for_device_update.assert_called_once_with(ANY, msg)

@pytest.mark.asyncio
async def test_teams_callback_token_refresh(macropad):
    msg = ServerMessage(tokenRefresh="new_token")
    macropad._current_state = None
    with patch("builtins.open", mock_open()) as mock_file:
        await macropad._teams_callback(msg)
        mock_file.assert_called_once_with("macropad-teams-token.txt", "w")
        mock_file().write.assert_called_once_with("new_token")

@pytest.mark.asyncio
async def test_update_device_status(macropad):
    macropad._current_state = ServerMessage(
        meetingUpdate=MeetingUpdate(
            meetingState=MeetingState(isInMeeting=True, isMuted=True, isHandRaised=False, isVideoOn=True),
            meetingPermissions=MeetingPermissions(canLeave=True)
        )
    )
    def send_msg(msg):
        future = asyncio.get_event_loop().create_future()
        future.set_result(None)
        assert isinstance(msg, SetLed)
        return future


    macropad._device.send_msg = Mock(side_effect=send_msg)
    macropad._virtual_macropad.send_msg = Mock()
    await macropad._update_device_status()
    assert macropad._device.send_msg.call_count == 4
    assert macropad._virtual_macropad.send_msg.call_count == 4



@pytest.mark.parametrize("msg_bytes, expected_action, should_call", [
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
])
@pytest.mark.asyncio
async def test_hid_callback_parametrized(macropad, msg_bytes, expected_action: MeetingAction, should_call):
    msg = Status(msg_bytes)
    macropad._websocket.send_message = AsyncMock()

    await macropad._hid_callback(msg)
    if should_call:
        macropad._websocket.send_message.assert_called_once()
        if expected_action:
            assert macropad._websocket.send_message.call_args[0][0].action.name == expected_action.name
    else:
        macropad._websocket.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_hid_callback_invalid_button(macropad):
    msg = Status([11,1,0,0,1])

    await macropad._hid_callback(msg)
    macropad._websocket.send_message.assert_not_called()
