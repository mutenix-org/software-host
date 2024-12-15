# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "hidapi",
#     "websockets",
#     "pydantic",
#     "requests",
# ]
# ///
__version__ = "1.0.0"

import hid
import asyncio
import logging
import concurrent.futures
from enum import IntEnum, Enum
import websockets
import argparse
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, ClassVar, override
import platform
from abc import ABC, abstractmethod
import requests

_logger = logging.getLogger(__name__)


def bring_teams_to_foreground() -> None:
    """Bring the Microsoft Teams window to the foreground."""
    if platform.system() == "Windows":
        import win32gui
        import win32con

        hwnd = win32gui.FindWindow(None, "Microsoft Teams")
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        else:
            _logger.info("Microsoft Teams window not found")
    elif platform.system() == "Darwin":
        import os

        os.system("osascript -e 'tell application \"Microsoft Teams\" to activate'")
        os.system(
            'osascript -e \'tell application "System Events" to tell process "Microsoft Teams" to set frontmost to true\''
        )
    elif platform.system() == "Linux":
        import os

        try:
            # Get the window ID of Microsoft Teams
            window_id = (
                os.system(["xdotool search --name Microsoft Teams"]).strip().decode()
            )
            # Activate the window
            os.system(f"xdotool windowactivate {window_id}")
        except Exception as e:
            _logger.info("Microsoft Teams window not found")
    else:
        _logger.error("Platform not supported")


# HID Messages and Commands
# InCommands are messages sent from the device to the host
# OutCommands are messages sent from the host to the device


class HidInCommands(IntEnum):
    """Identifiers for incoming HID messages."""

    VERSION_INFO = 0x99
    STATUS = 0x1


class HidOutCommands(IntEnum):
    """Identifiers for outgoing HID messages."""

    SET_LED = 0x1
    PING = 0xF0
    PREPARE_UPDATE = 0xE0
    RESET = 0xE1


class HidInputMessage:
    MESSAGE_LENGTH = 8

    @staticmethod
    def from_buffer(buffer: bytes):
        if buffer[1] == HidInCommands.VERSION_INFO.value:
            return VersionInfo(buffer[2:8])
        elif buffer[1] == HidInCommands.STATUS.value:
            return Status(buffer[2:8])
        raise NotImplementedError

    def __repr__(self):
        return self.__str__()


class Status(HidInputMessage):
    def __init__(self, buffer: bytes):
        self.buffer = buffer

    def __str__(self):
        return (
            f"Status {{ button: {self.button}, triggered: {self.triggered}, "
            f"doubletap: {self.doubletap}, pressed: {self.pressed}, "
            f"released: {self.released} }}"
        )

    @property
    def button(self):
        return self.buffer[0]

    @property
    def triggered(self) -> bool:
        return self.buffer[1] != 0

    @property
    def doubletap(self) -> bool:
        return self.buffer[2] != 0

    @property
    def pressed(self) -> bool:
        return self.buffer[3] != 0

    @property
    def released(self) -> bool:
        return self.buffer[4] != 0


class VersionInfo(HidInputMessage):
    def __init__(self, buffer: bytes):
        self.buffer = buffer

    def __str__(self):
        return f"Initialize {{ buffer: {self.buffer} }}"

    @property
    def version(self):
        return f"{self.buffer[0]}.{self.buffer[1]}.{self.buffer[2]}"


class HidOutputMessage:
    REPORT_ID = 1
    pass


class HidCommand(HidOutputMessage, ABC):
    @abstractmethod
    def to_buffer(self) -> bytes:
        raise NotImplementedError


class SetLed(HidCommand):
    RED = (0xFF, 0x00, 0x00, 0x00)
    GREEN = (0x00, 0xFF, 0x00, 0x00)
    BLUE = (0x00, 0x00, 0xFF, 0x00)
    WHITE = (0xFF, 0xFF, 0xFF, 0xFF)
    BLACK = (0x00, 0x00, 0x00, 0x00)
    YELLOW = (0xFF, 0xFF, 0x00, 0x00)
    CYAN = (0x00, 0xFF, 0xFF, 0x00)
    MAGENTA = (0xFF, 0x00, 0xFF, 0x00)
    ORANGE = (0xFF, 0xA5, 0x00, 0x00)
    PURPLE = (0x80, 0x00, 0x80, 0x00)

    def __init__(
        self, id, r=int | list[int], g: int = None, b: int = None, w: int = None
    ):
        self.id = id
        if isinstance(r, int):
            r = r, g, b, w
        if len(r) != 4:
            raise ValueError("Color must be a list of 4 integers")
        if any([c < 0 or c > 0xFF for c in r]):
            raise ValueError("Color values must be between 0 and 255")
        self.r, self.g, self.b, self.w = r

    @override
    def to_buffer(self) -> bytes:
        return bytes(
            [HidOutCommands.SET_LED, self.id, self.r, self.g, self.b, self.w, 0, 0]
        )


class SimpleHidCommand(HidCommand):
    def __init__(self, command: HidOutCommands):
        self.command = command

    @override
    def to_buffer(self) -> bytes:
        return bytes([int(self.command), 0, 0, 0, 0, 0, 0, 0])


class Ping(SimpleHidCommand):
    def __init__(self):
        super().__init__(HidOutCommands.PING)


class PrepareUpdate(SimpleHidCommand):
    def __init__(self):
        super().__init__(HidOutCommands.PREPARE_UPDATE)


class Reset(SimpleHidCommand):
    def __init__(self):
        super().__init__(HidOutCommands.RESET)


# Teams WebSocket Messages
# ServerMessage are messages sent from the server to the client
# ClientMessage are messages sent from the client to the server


class MeetingPermissions(BaseModel):
    """Permissions for the meeting communicated by teams."""

    can_toggle_mute: bool = Field(False, alias="canToggleMute")
    can_toggle_video: bool = Field(False, alias="canToggleVideo")
    can_toggle_hand: bool = Field(False, alias="canToggleHand")
    can_toggle_blur: bool = Field(False, alias="canToggleBlur")
    can_leave: bool = Field(False, alias="canLeave")
    can_react: bool = Field(False, alias="canReact")
    can_toggle_share_tray: bool = Field(False, alias="canToggleShareTray")
    can_toggle_chat: bool = Field(False, alias="canToggleChat")
    can_stop_sharing: bool = Field(False, alias="canStopSharing")
    can_pair: bool = Field(False, alias="canPair")


class MeetingState(BaseModel):
    """Current state of the meeting communicated by teams."""

    is_muted: bool = Field(False, alias="isMuted")
    is_hand_raised: bool = Field(False, alias="isHandRaised")
    is_in_meeting: bool = Field(False, alias="isInMeeting")
    is_recording_on: bool = Field(False, alias="isRecordingOn")
    is_background_blurred: bool = Field(False, alias="isBackgroundBlurred")
    is_sharing: bool = Field(False, alias="isSharing")
    has_unread_messages: bool = Field(False, alias="hasUnreadMessages")
    is_video_on: bool = Field(False, alias="isVideoOn")


class MeetingUpdate(BaseModel):
    meeting_permissions: Optional[MeetingPermissions] = Field(
        None, alias="meetingPermissions"
    )
    meeting_state: Optional[MeetingState] = Field(None, alias="meetingState")


class ServerMessage(BaseModel):
    request_id: Optional[int] = Field(None, alias="requestId")
    response: Optional[str] = None
    error_msg: Optional[str] = Field(None, alias="errorMsg")
    token_refresh: Optional[str] = Field(None, alias="tokenRefresh")
    meeting_update: Optional[MeetingUpdate] = Field(None, alias="meetingUpdate")


class ClientMessageParameterType(str, Enum):
    """Types of reactions for client messages."""

    ReactApplause = "applause"
    ReactLaugh = "laugh"
    ReactLike = "like"
    ReactLove = "love"
    ReactWow = "wow"
    ToggleUiChat = "chat"
    ToggleUiSharing = "sharing-tray"


class ClientMessageParameter(BaseModel):
    type_: ClientMessageParameterType = Field(..., serialization_alias="type")


class MeetingAction(str, Enum):
    NoneAction = "none"
    QueryMeetingState = "query-state"
    Mute = "mute"
    Unmute = "unmute"
    ToggleMute = "toggle-mute"
    HideVideo = "hide-video"
    ShowVideo = "show-video"
    ToggleVideo = "toggle-video"
    UnblurBackground = "unblur-background"
    BlurBackground = "blur-background"
    ToggleBlurBackground = "toggle-background-blur"
    LowerHand = "lower-hand"
    RaiseHand = "raise-hand"
    ToggleHand = "toggle-hand"
    LeaveCall = "leave-call"
    React = "send-reaction"
    ToggleUI = "toggle-ui"
    StopSharing = "stop-sharing"


class ClientMessage(BaseModel):
    action: MeetingAction
    parameters: Optional[ClientMessageParameter] = None
    request_id: int = Field(None, serialization_alias="requestId")

    _request_id_counter: ClassVar[int] = 0
    """Each message must have a unique request_id. The counter is incremented for each message automatically."""

    @classmethod
    def create(cls, *args, **kwargs) -> "ClientMessage":
        cls._request_id_counter += 1
        kwargs["request_id"] = cls._request_id_counter
        _logger.debug(f"Creating message with request_id: {cls._request_id_counter}")
        return cls(*args, **kwargs)


# Device Info is sent to the WebSocket server to identify the device
# the token should be stored after reception to identify the device


class Identifier:
    """Identifies the device to the Teams Websocket server."""

    def __init__(self, manufacturer, device, app, app_version, token=""):
        self.protocol_version = "2.0.0"
        self.manufacturer = manufacturer
        self.device = device
        self.app = app
        self.app_version = app_version
        self.token = token


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
        while True:
            _logger.info(
                f"Looking for device with VID: {self._vid:x} PID: {self._pid:x}"
            )
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


class WebSocketClient:
    """Handles the WebSocket connection to Teams."""

    def __init__(self, uri: str, identifier: Identifier):
        self._uri = uri
        self._connection = None
        self._send_queue = asyncio.Queue()
        self._callback = None
        params = f"?protocol-version={identifier.protocol_version}&manufacturer={identifier.manufacturer}&device={identifier.device}&app={identifier.app}&app-version={identifier.app_version}&token={identifier.token}"
        self._uri += params
        self._connecting = False

    async def _connect(self):
        if self._connecting:
            _logger.debug("Other connection in progress, wait for completion")
            while self._connecting:
                await asyncio.sleep(0.1)
            return
        self._connecting = True
        while True:
            try:
                self.connection = await websockets.connect(self._uri)
                _logger.info(f"Connected to WebSocket server at {self._uri}")
                break
            except Exception as e:
                _logger.info(f"Failed to connect to WebSocket server: {e}")
                await asyncio.sleep(1)
        self._connecting = False

    def send_message(self, message: ClientMessage):
        future = asyncio.get_event_loop().create_future()
        self._send_queue.put_nowait((message, future))
        return future

    def register_callback(self, callback: callable):
        self._callback = callback

    async def _send_loop(self):
        while True:
            message, future = await self._send_queue.get()
            try:
                msg = message.model_dump_json(by_alias=True)
                await self.connection.send(msg)
                future.set_result(True)
            except ValidationError as e:
                _logger.error("Unpackable message: %s", message)
                _logger.error("Error: %s", e)
                future.set_exception(e)
            except Exception as e:
                future.set_exception(e)
                await self._connect()
            finally:
                self._send_queue.task_done()

    async def _receive_loop(self):
        while True:
            try:
                message = await self.connection.recv()
                message = ServerMessage.model_validate_json(message)
                if self._callback:
                    if asyncio.iscoroutinefunction(self._callback):
                        asyncio.create_task(self._callback(message))
                    else:
                        self._callback(message)
            except Exception as e:
                _logger.error(f"Error receiving message: {e}")
                await self._connect()

    async def process(self):
        while True:
            try:
                await self._connect()
                await asyncio.gather(self._send_loop(), self._receive_loop())
            except Exception as e:
                _logger.info("Error processing WebSocket connection: %s", e)


class Macropad:
    def __init__(self, vid=0x2E8A, pid=0x2083):
        self._version_seen = None
        self._setup(vid, pid)

    def _setup(self, vid=0x2E8A, pid=0x2083):
        self.device = HidDevice(vid, pid)
        try:
            with open("macropad-teams-token.txt", "r") as f:
                token = f.read()
        except FileNotFoundError:
            token = ""
        self.websocket = WebSocketClient(
            "ws://127.0.0.1:8124",
            Identifier(
                manufacturer="test",
                device="test",
                app="test",
                app_version="1.0.0",
                token=token,
            ),
        )
        self.websocket.register_callback(self._teams_callback)
        self.device.register_callback(self._hid_callback)

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

                await self.websocket.send_message(client_message)
        elif isinstance(msg, VersionInfo):
            if self._version_seen != msg.version:
                _logger.info(f"Version Info: {msg}")
                self._version_seen = msg.version
            else:
                _logger.debug(f"Version Info: {msg}")

    async def _teams_callback(self, msg: ServerMessage):
        _logger.debug("Teams message: %s", msg)
        if msg.token_refresh:
            try:
                with open("macropad-teams-token.txt", "w") as f:
                    f.write(msg.token_refresh)
            except IOError as e:
                _logger.error(f"Failed to write token to file: {e}")
        msgs = []

        def set_led(id, condition, true_color, false_color):
            if condition:
                msgs.append(SetLed(id, true_color))
            else:
                msgs.append(SetLed(id, false_color))

        if msg.meeting_update:
            if msg.meeting_update.meeting_state:
                state = msg.meeting_update.meeting_state
                if state.is_in_meeting:
                    set_led(1, state.is_muted, SetLed.RED, SetLed.GREEN)
                    set_led(2, state.is_hand_raised, SetLed.YELLOW, SetLed.WHITE)
                    set_led(3, state.is_video_on, SetLed.GREEN, SetLed.RED)
                else:
                    for i in range(5):
                        set_led(i, False, SetLed.BLACK, SetLed.BLACK)

            if msg.meeting_update.meeting_permissions:
                permissions = msg.meeting_update.meeting_permissions
                set_led(5, permissions.can_leave, SetLed.GREEN, SetLed.BLACK)

        for m in msgs:
            await self.device.send_msg(m)

    async def process(self):
        """Starts the process loop for the device and the WebSocket connection."""
        try:
            await asyncio.gather(self.device.process(), self.websocket.process())
        except Exception as e:
            _logger.error(f"Error in Macropad process: {e}")
            
def check_for_device_update():
    try:
        requests.get("https://m42e.de/mutenix/macropad/latest")
    except requests.RequestException as e:
        _logger.error("Failed to check for device update availability")
        
def check_for_self_update():
    try:
        requests.get("https://m42e.de/mutenix/software/latest")
    except requests.RequestException as e:
        _logger.error("Failed to check for device update availability")

    


async def main():
    macropad = Macropad(vid=0x2E8A, pid=0x2083)
    await macropad.process()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
