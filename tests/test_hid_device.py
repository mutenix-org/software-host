from __future__ import annotations

import asyncio
import tracemalloc
from unittest.mock import ANY
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from mutenix.hid_commands import HidOutputMessage
from mutenix.hid_commands import Ping
from mutenix.hid_commands import PrepareUpdate
from mutenix.hid_device import HidDevice

tracemalloc.start()


@pytest.fixture
def hid_device():
    with patch("hid.device") as MockHidDevice:
        MockHidDevice.return_value = Mock()
        return HidDevice(vid=0x1234, pid=0x5678)


@pytest.mark.asyncio
async def test_wait_for_device(hid_device):
    with patch.object(
        hid_device._device,
        "open",
        side_effect=Exception("Device not found"),
    ):
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await hid_device._wait_for_device()


@pytest.mark.asyncio
async def test_send_msg(hid_device):
    msg = HidOutputMessage()
    future = hid_device.send_msg(msg)
    assert not future.done()
    assert not hid_device._send_buffer.empty()


@pytest.mark.asyncio
async def test_register_callback(hid_device):
    callback = Mock()
    hid_device.register_callback(callback)
    assert callback in hid_device._callbacks


@pytest.mark.asyncio
async def test_ping(hid_device):
    with patch.object(hid_device, "send_msg", return_value=Mock()):
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await hid_device._ping()


@pytest.mark.asyncio
async def test_write_success(hid_device):
    msg = HidOutputMessage()
    future = hid_device.send_msg(msg)
    with patch.object(hid_device, "_send_report", return_value=1):
        await hid_device._write()
    assert future.done()
    assert future.result() == 1


@pytest.mark.asyncio
async def test_write_failure(hid_device):
    msg = HidOutputMessage()
    future = hid_device.send_msg(msg)
    with patch.object(hid_device, "_send_report", return_value=-1):
        await hid_device._write()
    assert future.done()
    assert future.exception() is not None


@pytest.mark.asyncio
async def test_write_device_disconnected(hid_device):
    msg = HidOutputMessage()
    future = hid_device.send_msg(msg)
    with patch.object(
        hid_device,
        "_send_report",
        side_effect=OSError("Device disconnected"),
    ):
        await hid_device._write()
    assert not future.done()


@pytest.mark.asyncio
async def test_write_value_error(hid_device):
    msg = HidOutputMessage()
    future = hid_device.send_msg(msg)
    with patch.object(
        hid_device,
        "_send_report",
        side_effect=ValueError("Invalid message"),
    ):
        await hid_device._write()
    assert not future.done()


@pytest.mark.asyncio
async def test_read_success(hid_device):
    data = bytes([0x01, 0x02, 0x03])
    future = asyncio.get_event_loop().create_future()

    async def callback(msg):
        future.set_result(msg)

    hid_device._callbacks.append(callback)
    with patch.object(hid_device._device, "read", new_callable=Mock, return_value=data):
        with patch(
            "mutenix.hid_commands.HidInputMessage.from_buffer",
            return_value=Mock(),
        ):
            await hid_device._read()
    await future


@pytest.mark.asyncio
async def test_read_device_disconnected(hid_device):
    hid_device._wait_for_device = AsyncMock()
    with patch.object(
        hid_device._device,
        "read",
        side_effect=OSError("Device disconnected"),
    ):
        with patch("mutenix.hid_device._logger.error") as mock_logger:
            await hid_device._read()
            mock_logger.assert_called_with("Device disconnected: %s", ANY)

    assert hid_device._wait_for_device.called


@pytest.mark.asyncio
async def test_read_value_error(hid_device):
    with patch.object(
        hid_device._device,
        "read",
        side_effect=ValueError("Invalid message"),
    ):
        with patch("mutenix.hid_device._logger.error") as mock_logger:
            await hid_device._read()
            mock_logger.assert_called_with(
                "Error reading message: %s",
                ANY,
            )


class TypeMatcher:
    def __init__(self, expected_type):
        self.expected_type = expected_type

    def __eq__(self, other):
        return isinstance(other, self.expected_type)


@pytest.mark.asyncio
async def test_ping_sends_ping_message(hid_device):
    hid_device._last_communication = asyncio.get_event_loop().time() - 5
    with patch.object(hid_device, "send_msg") as mock_send_msg:
        await hid_device._ping()
        mock_send_msg.assert_called_once_with(TypeMatcher(Ping))


@pytest.mark.asyncio
async def test_ping_resets_last_communication(hid_device):
    initial_time = asyncio.get_event_loop().time()
    with patch("asyncio.get_event_loop", return_value=asyncio.get_event_loop()):
        with patch.object(hid_device, "send_msg"):
            await hid_device._ping()
            assert hid_device._last_ping_time >= initial_time


class RoundAboutMatcher:
    def __init__(self, expected_value, offset):
        self.expected_value = expected_value
        self.offset = offset

    def __eq__(self, other):
        return abs(other - self.expected_value) < self.offset


@pytest.mark.asyncio
async def test_ping_waits_before_sending(hid_device):
    hid_device._last_ping_time = asyncio.get_event_loop().time()
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with patch.object(hid_device, "send_msg"):
            await hid_device._ping()
            mock_sleep.assert_called_with(RoundAboutMatcher(4.5, 0.2))


# test


@pytest.mark.asyncio
async def test_send_report_success(hid_device):
    msg = PrepareUpdate()
    with patch.object(hid_device._device, "write", return_value=1) as mock_write:
        result = hid_device._send_report(msg)
        assert result == 1
        mock_write.assert_called_once_with(bytes([msg.REPORT_ID]) + msg.to_buffer())


@pytest.mark.asyncio
async def test_send_report_failure(hid_device):
    msg = PrepareUpdate()
    with patch.object(hid_device._device, "write", return_value=-1) as mock_write:
        result = hid_device._send_report(msg)
        assert result == -1
        mock_write.assert_called_once_with(bytes([msg.REPORT_ID]) + msg.to_buffer())


@pytest.mark.asyncio
async def test_send_report_exception(hid_device):
    msg = PrepareUpdate()
    with patch.object(
        hid_device._device, "write", side_effect=OSError("Device error"),
    ) as mock_write:
        with pytest.raises(OSError, match="Device error"):
            hid_device._send_report(msg)
        mock_write.assert_called_once_with(bytes([msg.REPORT_ID]) + msg.to_buffer())


@pytest.mark.asyncio
async def test_unregister_callback():
    # Create a HidDevice instance
    device = HidDevice(vid=0x1234, pid=0x5678)

    # Create a mock callback
    callback = Mock()

    # Register the callback
    device.register_callback(callback)
    assert callback in device._callbacks

    # Unregister the callback
    device.unregister_callback(callback)
    assert callback not in device._callbacks

    # Try to unregister the callback again (should not raise an error)
    device.unregister_callback(callback)
    assert callback not in device._callbacks


@pytest.mark.asyncio
async def test_search_for_device_success(hid_device):
    with patch("hid.device") as MockHidDevice:
        mock_device = MockHidDevice.return_value
        mock_device.open.return_value = None
        mock_device.set_nonblocking.return_value = None

        device = await hid_device._search_for_device()

        assert device is not None
        mock_device.open.assert_called_once_with(hid_device._vid, hid_device._pid)
        mock_device.set_nonblocking.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_search_for_device_failure(hid_device):
    with patch("hid.device") as MockHidDevice:
        mock_device = MockHidDevice.return_value
        mock_device.open.side_effect = Exception("Device not found")

        device = await hid_device._search_for_device()

        assert device is None
        mock_device.open.assert_called_once_with(hid_device._vid, hid_device._pid)


@pytest.mark.asyncio
async def test_invoke_callbacks_sync(hid_device):
    callback = Mock()
    hid_device.register_callback(callback)
    msg = Mock()
    hid_device._invoke_callbacks(msg)
    callback.assert_called_once_with(msg)


@pytest.mark.asyncio
async def test_invoke_callbacks_async(hid_device):
    async def async_callback(msg):
        async_callback.called = True

    async_callback.called = False
    hid_device.register_callback(async_callback)
    msg = Mock()
    hid_device._invoke_callbacks(msg)
    await asyncio.sleep(0)  # Allow the async callback to be called
    assert async_callback.called


@pytest.mark.asyncio
async def test_invoke_callbacks_mixed(hid_device):
    callback = Mock()

    async def async_callback(msg):
        async_callback.called = True

    async_callback.called = False
    hid_device.register_callback(callback)
    hid_device.register_callback(async_callback)
    msg = Mock()
    hid_device._invoke_callbacks(msg)
    callback.assert_called_once_with(msg)
    await asyncio.sleep(0)  # Allow the async callback to be called
    assert async_callback.called
