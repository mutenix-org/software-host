# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import asyncio
import logging
from typing import Callable

import hid
from mutenix.models.config import DeviceInfo
from mutenix.models.hid_commands import HidCommand
from mutenix.models.hid_commands import HidInputMessage
from mutenix.models.hid_commands import Ping
from mutenix.models.state import ConnectionState
from mutenix.models.state import HardwareState
from mutenix.utils import block_parallel
from mutenix.utils import rate_limited_logger
from mutenix.utils import run_loop
from mutenix.utils import run_till_some_loop

_logger = logging.getLogger(__name__)


class HidDevice:
    """Handles the HID connection to the device.
    Providing async read and write loops for incoming and outgoing messages.
    """

    def __init__(
        self,
        state: HardwareState,
        device_identifications: list[DeviceInfo] | None = None,
    ):
        self._state = state
        self._device_info = device_identifications or []
        self._device: hid.device | None = None
        self._callbacks: list[Callable[[HidInputMessage], None]] = []
        self._send_buffer: asyncio.Queue[tuple[HidCommand, asyncio.Future]] = (
            asyncio.Queue()
        )
        self._last_communication: float = 0
        self._last_ping_time: float = 0
        self._waiting_for_device: bool = False
        self._run: bool = True

    def __del__(self):
        if self._device:
            self._device.close()

    @block_parallel
    async def _wait_for_device(self):
        _logger.info(
            "Looking for device with",
        )
        self._device = None
        self._state.connection_status = ConnectionState.DISCONNECTED
        self._device = await self._search_for_device_loop()
        if self._device:
            self._set_hardware_info()

    def _set_hardware_info(self):
        if self._device:
            self._state.serial_number = self._device.get_serial_number_string()
            self._state.manufacturer = self._device.get_manufacturer_string()
            self._state.product = self._device.get_product_string()
            self._state.connection_status = ConnectionState.CONNECTED

    def _open_device_with_info(self, device_info: DeviceInfo):
        device = hid.device()
        if device_info["product_id"] == 0 and device_info["vendor_id"] == 0:
            try:
                device.open(
                    product_id=0,
                    vendor_id=0,
                    serial_number=device_info["serial_number"],
                )
                return device
            except Exception as e:
                _logger.debug("Could not open device by serial number %s", e)
        else:
            try:
                device.open(
                    product_id=device_info["product_id"],
                    vendor_id=device_info["vendor_id"],
                    serial_number=device_info["serial_number"],
                )
                return device
            except Exception as e:
                _logger.debug("Could not open HID Connection (%s)", e)
        return None

    async def _search_for_device(self):
        try:

            def find_device():
                devices = []
                for device in sorted(
                    hid.enumerate(),
                    key=lambda x: x["bus_type"],
                    reverse=True,
                ):
                    if "mutenix" in device["product_string"].lower():
                        _logger.info("Device found %s", device)
                        devices.append(device)
                return devices

            if not self._device_info or len(self._device_info) == 0:
                available_devices = find_device()
            else:
                available_devices = list(
                    map(lambda x: x.model_dump(), self._device_info),
                )
            if len(available_devices) == 0:
                _logger.error("No device available, no config")
                await asyncio.sleep(0)
                return None
            _logger.debug("Looking for device with %s", available_devices)
            device = hid.device()
            # We are sorting the devices by vendor_id to make sure we try to open BT device first
            for device_info in sorted(available_devices, key=lambda x: x["vendor_id"]):
                if device := self._open_device_with_info(device_info):
                    break
                _logger.debug("Device not found %s", device_info)
            else:
                return None
            _logger.info("Device found %s", device)
            device.set_nonblocking(1)
            return device
        except Exception as e:
            _logger.debug("Failed to get device: %s", e)
            return None

    def _send_report(self, data: HidCommand):
        buffer = bytes([data.REPORT_ID]) + data.to_buffer()
        buffer = bytes(buffer)
        if not self._device:
            raise ValueError("Device not connected")
        return self._device.write(buffer)

    def send_msg(self, msg: HidCommand):
        """
        Sends a HID output message asynchronously.

        Args:
            msg (HidOutputMessage): The HID output message to be sent.

        Returns:
            asyncio.Future: A future that will be set when the message is processed.
        """
        future = asyncio.get_event_loop().create_future()
        self._send_buffer.put_nowait((msg, future))
        _logger.debug("Put message")
        return future

    def register_callback(self, callback: Callable[[HidInputMessage], None]) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[HidInputMessage], None]) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _invoke_callbacks(self, msg: HidInputMessage) -> None:
        for callback in self._callbacks:
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(msg))
            else:
                callback(msg)

    @rate_limited_logger(_logger, limit=3, interval=10)
    def _log_failed_to_send(self, *args, **kwargs):
        _logger.error(*args, **kwargs)

    async def _read(self) -> None:
        try:
            if not self._device:
                await asyncio.sleep(0.1)  # pragma: no cover
                return
            buffer: bytes = self._device.read(64)
            if not buffer or len(buffer) == 0:
                await asyncio.sleep(0.1)  # pragma: no cover
            else:
                msg = HidInputMessage.from_buffer(buffer)
                self._invoke_callbacks(msg)
        except OSError as e:  # Device disconnected
            _logger.error("Device disconnected: %s", e)
            await self._wait_for_device()
            _logger.info("Device reconnected")
        except Exception as e:
            _logger.error("Error reading message: %s", e)

    async def _write(self) -> None:
        try:
            msg, future = await self._send_buffer.get()
            _logger.debug("Sending message: %s", msg)
            result = self._send_report(msg)
            if result < 0:
                self._log_failed_to_send("Failed to send message: %s", msg)
                future.set_exception(Exception("Failed to send message"))
                return
            self._last_communication = asyncio.get_event_loop().time()
            if not future.cancelled():
                future.set_result(result)
            self._send_buffer.task_done()
        except OSError as e:  # Device disconnected
            _logger.error("Device disconnected: %s", e)
            future.set_exception(e)
            await self._wait_for_device()
        except ValueError as e:
            _logger.error("Error sending message: %s", e)
            future.set_exception(e)
            await self._wait_for_device()

    async def _ping(self) -> None:
        """
        Sends a ping message to the HID device.
        """
        await asyncio.sleep(
            self._last_ping_time + 4.5 - asyncio.get_event_loop().time(),
        )
        if asyncio.get_event_loop().time() - self._last_ping_time > 4.5:
            _logger.debug("Sending ping")
            msg = Ping()
            future = self.send_msg(msg)
            try:
                self._last_ping_time = asyncio.get_event_loop().time()
                await future
                _logger.debug("ping finally sent")
            except Exception as e:
                self._log_failed_to_send("Failed to send ping: %s", e)
            self._last_ping_time = asyncio.get_event_loop().time()

    async def _process(self) -> None:  # pragma: no cover
        await self._wait_for_device()
        await asyncio.gather(self._read_loop(), self._write_loop(), self._ping_loop())

    async def process(self) -> None:  # pragma: no cover
        await self._process_loop()

    async def stop(self) -> None:  # pragma: no cover
        self._run = False

    # create the run loops
    _read_loop = run_loop(_read)
    _write_loop = run_loop(_write)
    _ping_loop = run_loop(_ping)
    _process_loop = run_loop(_process)
    _search_for_device_loop = run_till_some_loop(sleep_time=1)(_search_for_device)

    @property
    def raw(self) -> hid.device | None:  # pragma: no cover
        return self._device

    async def wait_for_device(self) -> None:  # pragma: no cover
        await self._wait_for_device()

    @property
    def connected(self) -> bool:  # pragma: no cover
        return self._device is not None
