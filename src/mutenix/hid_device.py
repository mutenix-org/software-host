import asyncio
from typing import Callable
import hid
import logging

from mutenix.hid_commands import HidCommand, HidOutputMessage, HidInputMessage, Ping
from mutenix.utils import run_loop, block_parallel, run_till_some_loop

_logger = logging.getLogger(__name__)


class HidDevice:
    """Handles the HID connection to the device.
    Providing async read and write loops for incoming and outgoing messages.
    """

    def __init__(self, vid: int, pid: int):
        self._vid = vid
        self._pid = pid
        self._device: hid.device = hid.device()
        self._callbacks: list[Callable[[HidInputMessage], None]] = []
        self._send_buffer: asyncio.Queue = asyncio.Queue()
        self._last_communication = 0
        self._waiting_for_device = False
        self._run = True

    def __del__(self):
        self._device.close()

    @block_parallel
    async def _wait_for_device(self):
        _logger.info(
            f"Looking for device with VID: {self._vid:x} PID: {self._pid:x}"
        )
        await self._search_for_device_loop()

    async def _search_for_device(self):
        try:
            device = hid.device()
            device.open(self._vid, self._pid)
            device.set_nonblocking(0)
            _logger.info("Device found %s", device)
            return device
        except Exception as e:
            _logger.debug("Failed to get device: %s", e)
            return None

    def _send_report(self, data: HidCommand):
        buffer = bytes([data.REPORT_ID]) + data.to_buffer()
        buffer = bytes(buffer)
        return self._device.write(buffer)

    def send_msg(self, msg: HidOutputMessage):
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

    def register_callback(self, callback):
        """
        Registers a callback function to be called when an event occurs.

        Args:
            callback (function): The callback function to register.

        Returns:
            None
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback):
        """
        Unregisters a callback function from the list of callbacks.

        Args:
            callback (function): The callback function to be removed from the list of registered callbacks.

        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _invoke_callbacks(self, msg):
        for callback in self._callbacks:
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(msg))
            else:
                callback(msg)

    async def _read(self):
        try:
            buffer = await self._device.read(64, timeout_ms=100)
            if buffer and len(buffer):
                msg = HidInputMessage.from_buffer(buffer)
                self._invoke_callbacks(msg)
        except OSError as e:  # Device disconnected
            _logger.error("Device disconnected: %s", e)
            await self._wait_for_device()
            _logger.info("Device reconnected")
        except Exception as e:
            _logger.error("Error reading message: %s", e)


    async def _write(self):
        try:
            msg, future = await self._send_buffer.get()
            result = self._send_report(msg)
            if result < 0:
                _logger.error("Failed to send message: %s", msg)
                future.set_exception(Exception("Failed to send message"))
                return
            self._last_communication = asyncio.get_event_loop().time()
            if not future.cancelled():
                future.set_result(result)
            self._send_buffer.task_done()
        except OSError as e:  # Device disconnected
            _logger.error("Device disconnected: %s", e)
        except ValueError as e:
            _logger.error("Error sending message: %s", e)


    async def _ping(self):
        """
        Sends a ping message to the HID device.
        """
        await asyncio.sleep(
            self._last_communication + 4.5 - asyncio.get_event_loop().time()
        )
        if asyncio.get_event_loop().time() - self._last_communication > 4.5:
            _logger.debug("Sending ping")
            msg = Ping()
            self.send_msg(msg)
            self._last_communication = asyncio.get_event_loop().time()


    async def _process(self):
        await self._wait_for_device()
        await asyncio.gather(self._read_loop(), self._write_loop(), self._ping_loop())


    async def process(self):
        """
        Processes the HID device by running the internal process loop.

        Returns:
            None
        """
        await self._process_loop()

    async def stop(self):
        """
        Stops the HID device by setting the internal run flag to False.

        Signals the processing loops to stop.
        """
        self._run = False

    # create the run loops
    _read_loop = run_loop(_read)
    _write_loop = run_loop(_write)
    _ping_loop = run_loop(_ping)
    _process_loop = run_loop(_process)
    _search_for_device_loop = run_till_some_loop(sleep_time=1)(_search_for_device)