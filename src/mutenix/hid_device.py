import asyncio
import concurrent.futures
import hid
import logging

from mutenix.hid_commands import HidOutputMessage, HidInputMessage, Ping

_logger = logging.getLogger(__name__)

class HidDevice:
    """Handles the HID connection to the device.
    Providing async read and write loops for incoming and outgoing messages.
    """

    def __init__(self, vid: int, pid: int):
        self._vid = vid
        self._pid = pid
        self._device = hid.device()
        self._callback = None
        self._send_buffer = asyncio.Queue()
        self._last_communication = 0
        self._waiting_for_device = False

    def __del__(self):
        self._device.close()

    async def _wait_for_device(self):
        if self._waiting_for_device:
            while self._waiting_for_device:
                await asyncio.sleep(0.1)
            return
        self._waiting_for_device = True
        searching = False
        while True:
            if not searching:
                _logger.info(
                    f"Looking for device with VID: {self._vid:x} PID: {self._pid:x}"
                )
            searching = True
            try:
                self._device = hid.device()
                self._device.open(self._vid, self._pid)
                _logger.info("Device found %s", self._device)
                _logger.info(self._device.set_nonblocking(0))
                break
            except Exception as e:
                _logger.debug("Failed to get device: %s", e)
                await asyncio.sleep(1)
        self._waiting_for_device = False

    def _send_report(self, data: HidOutputMessage):
        buffer = bytes([data.REPORT_ID]) + data.to_buffer()
        buffer = bytes(buffer)
        return self._device.write(buffer)

    def send_msg(self, msg: HidOutputMessage):
        future = asyncio.get_event_loop().create_future()
        self._send_buffer.put_nowait((msg, future))
        _logger.debug("Put message")
        return future

    def register_callback(self, callback):
        self._callback = callback

    async def _read(self) -> bytes:
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, self._device.read, 64)
        return result

    async def _read_loop(self):
        while True:
            try:
                buffer = await self._read()
                if buffer:
                    msg = HidInputMessage.from_buffer(buffer)
                    if self._callback:
                        if asyncio.iscoroutinefunction(self._callback):
                            asyncio.create_task(self._callback(msg))
                        else:
                            self._callback(msg)
            except OSError as e:  # Device disconnected
                _logger.error("Device disconnected: %s", e)
                await self._wait_for_device()

    async def _write_loop(self):
        """
        Continuously sends messages from the send buffer to the HID device.

        This method runs in an infinite loop, retrieving messages from the send buffer
        and sending them to the HID device. It sets the result of the future associated
        with each message once the message is sent.
        """
        while True:
            try:
                msg, future = await self._send_buffer.get()
                result = self._send_report(msg)
                if result < 0:
                    _logger.error("Failed to send message: %s", msg)
                    future.set_exception(Exception("Failed to send message"))
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
        while True:
            await asyncio.sleep(
                self._last_communication + 4.5 - asyncio.get_event_loop().time()
            )
            if asyncio.get_event_loop().time() - self._last_communication > 4.5:
                _logger.debug("Sending ping")
                msg = Ping()
                self.send_msg(msg)
                self._last_communication = asyncio.get_event_loop().time()

    async def process(self):
        """
        Starts the read and write loops to process incoming and outgoing HID messages.
        """
        while True:
            await self._wait_for_device()
            await asyncio.gather(self._read_loop(), self._write_loop(), self._ping())
