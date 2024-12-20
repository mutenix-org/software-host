# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "hidapi",
#     "websockets",
#     "pydantic",
#     "requests",
#     "pywin32; platform_system=='Windows'",
#     "pywinauto; platform_system=='Windows'",
#     "aiohttp",
#     "tqdm",
#     "semver",
# ]
# ///

__version__ = "1.0.0"

# region: imports
import asyncio
import concurrent.futures
import hid
import io
import json
import logging
import os
import pathlib
import platform
import requests
import semver
import tarfile
import tempfile
import time
import websockets

from abc import ABC, abstractmethod
from aiohttp import web
from enum import IntEnum, Enum, ReprEnum
from pydantic import BaseModel, Field, ValidationError
from tqdm import tqdm
from typing import Optional, ClassVar, override

if platform.system().lower() == "windows":
    from pywinauto.findwindows import find_windows
    from pywinauto.win32functions import SetFocus
    import win32gui
    import win32con
elif platform.system().lower() == "linux":
    import subprocess

# endregion


# region: Logging

# Configure logging to write to a file
log_file_path = pathlib.Path(__file__).parent / "macropad.log"
logging.basicConfig(
    level=logging.INFO,
    filename=log_file_path,
    filemode="a",
    format="%(asctime)s - %(name)s - %(levelname)-8s - %(message)s",
)
_logger = logging.getLogger(__name__)

# endregion


# region: Teams foreground activation


def bring_teams_to_foreground() -> None:
    """Bring the Microsoft Teams window to the foreground."""
    if platform.system().lower() == "windows":
        window_id = find_windows(title_re=".*Teams.*")
        _logger.debug(window_id)
        for w in window_id:
            win32gui.ShowWindow(w, win32con.SW_MINIMIZE)
            win32gui.ShowWindow(w, win32con.SW_RESTORE)
            win32gui.SetActiveWindow(w)

    elif platform.system().lower() == "darwin":
        os.system("osascript -e 'tell application \"Microsoft Teams\" to activate'")
        os.system(
            'osascript -e \'tell application "System Events" to tell process "Microsoft Teams" to set frontmost to true\''
        )
    elif platform.system().lower() == "linux":
        try:
            # Get the window ID of Microsoft Teams
            window_id = (
                subprocess.check_output(
                    "xdotool search --name 'Microsoft Teams'", shell=True
                )
                .strip()
                .decode()
            )
            # Activate the window
            os.system(f"xdotool windowactivate {window_id}")
        except Exception as e:
            _logger.error("Microsoft Teams window not found: %s", e)
    else:
        _logger.error("Platform not supported")


# endregion


# region HID Device Messages and Commands
class HardwareTypes(IntEnum):
    """Hardware types for the Macropad."""

    UNKNOWN = 0x00
    SINGLE_BUTTON = 0x01
    FIVE_BUTTON_USB = 0x02
    FIVE_BUTTON_BT = 0x03
    TEN_BUTTON_USB = 0x04
    TEN_BUTTON_BT = 0x05


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
        return f"Version Info: {self.version}, type {self.type.name}"

    @property
    def version(self):
        return f"{self.buffer[0]}.{self.buffer[1]}.{self.buffer[2]}"

    @property
    def type(self):
        return HardwareTypes(self.buffer[3])


class HidOutputMessage:
    REPORT_ID = 1
    pass


class HidCommand(HidOutputMessage, ABC):
    @abstractmethod
    def to_buffer(self) -> bytes:
        raise NotImplementedError


class LedColor(tuple, ReprEnum):
    # The colors are encoded Green, Red, Blue, White
    RED = (0x00, 0x0A, 0x00, 0x00)
    GREEN = (0x0A, 0x00, 0x00, 0x00)
    BLUE = (0x00, 0x00, 0x0A, 0x00)
    WHITE = (0x00, 0x00, 0x00, 0x0A)
    BLACK = (0x00, 0x00, 0x00, 0x00)
    YELLOW = (0x0A, 0x0A, 0x00, 0x00)
    CYAN = (0x0A, 0x00, 0x0A, 0x00)
    MAGENTA = (0x00, 0x0A, 0x0A, 0x00)
    ORANGE = (0x08, 0x0A, 0x00, 0x00)
    PURPLE = (0x00, 0x09, 0x09, 0x00)


class SetLed(HidCommand):
    def __init__(self, id, led_color: LedColor):
        self.id = id
        self.color = led_color

    @override
    def to_buffer(self) -> bytes:
        color = self.color.value
        return bytes(
            [
                HidOutCommands.SET_LED,
                self.id,
                color[0],
                color[1],
                color[2],
                color[3],
                0,
                0,
            ]
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


# endregion


# region: Teams WebSocket Messages
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
    """Message sent to the Teams WebSocket server."""

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


# endregion


class Identifier:
    """Identifies the device to the Teams Websocket server.
    The token is used to authenticate the device with the server. It is received once the user
    allows the device to connect to Teams."""

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
                check_for_device_update(msg)
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
                self._virtual_macropad.send_msg(m).add_done_callback(
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


class VirtualMacropad:
    """A virtual representation of the Macropad for testing or playing around."""

    def __init__(self, host="127.0.0.1", port=8080):
        self.host = host
        self.port = port
        self._callback = None
        self.app = web.Application()
        self.app.add_routes(
            [
                web.get("/", self.index),
                web.post("/button", self.button_handler),
                web.get("/ws", self.websocket_handler),
            ]
        )
        self._websockets = set()
        self._led_status = {}

    def register_callback(self, callback):
        self._callback = callback

    async def index(self, request):
        return web.Response(
            text="""
            <html>
            <body>
            <div id="mainDiv" style="background-color: black; border-radius: 10px; padding: 20px; display: flex; flex-direction: column; align-items: center; width: 150px;">
            <div style="display: flex; align-items: center;">
                <button style="background-color: green; border-radius: 50%; margin: 5px; padding: 30px;" title="(Un)Mute" onclick="sendButtonPress(1)"></button>
                <div id="indicator1" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            <div style="display: flex; align-items: center;">
                <button style="background-color: yellow; border-radius: 50%; margin: 5px; padding: 30px;" title="Lower/Raise Hand" onclick="sendButtonPress(2)"></button>
                <div id="indicator2" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            <div style="display: flex; align-items: center;">
                <button style="background-color: black; color:white; border-radius: 50%; margin: 5px; padding: 30px;" title="Show Teams" onclick="sendButtonPress(3)"></button>
                <div id="indicator3" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            <div style="display: flex; align-items: center;">
                <button style="background-color: blue; border-radius: 50%; margin: 5px; padding: 30px;" title="Like" onclick="sendButtonPress(4)"></button>
                <div id="indicator4" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            <div style="display: flex; align-items: center;">
                <button style="background-color: red; border-radius: 50%; margin: 5px; padding: 30px;" title="Leave Call" onclick="sendButtonPress(5)"></button>
                <div id="indicator5" style="background-color: white; border-radius: 50%; width: 20px; height: 20px; margin-left: 10px;"></div>
            </div>
            </div>
            <button onclick="openPopup()">Open in Popup</button>
            <script>
            function openPopup() {
                const mainDiv = document.getElementById('mainDiv');
                const width = mainDiv.offsetWidth;
                const height = mainDiv.offsetHeight;
                const popup = window.open('', 'popup', `width=${width+20},height=${height+20},toolbar=no,location=no,status=no,menubar=no,scrollbars=yes,resizable=yes`);
                popup.document.write(document.documentElement.outerHTML);
                popup.document.close();
                popup.focus();
            }
            </script>
            <script>
            const ws = new WebSocket('ws://' + window.location.host + '/ws');
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                document.getElementById('indicator' + data.button).style.backgroundColor = data.color;
            };
            async function sendButtonPress(button) {
                ws.send(JSON.stringify({button: button}));
            }
            ws.onopen = function() {
                ws.send(JSON.stringify({state_request: true}));
            };
            setInterval(() => {
                ws.send(JSON.stringify({state_request: true}));
            }, 5000);
            </script>
            </body>
            </html>
        """,
            content_type="text/html",
        )

    async def button_handler(self, request):
        data = await request.json()
        button = data.get("button")
        if self._callback:
            msg = Status(bytes([button, 1, 0, 0, 1]))
            await self._callback(msg)
        return web.Response(status=200)

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._websockets.add(ws)
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "button" in data:
                    button = data.get("button")
                    if self._callback:
                        msg = Status(bytes([button, 1, 0, 0, 1]))
                        await self._callback(msg)
                if "state_request" in data:
                    for i, color in self._led_status.items():
                        if color:
                            await ws.send_json({"button": i, "color": color})
        self._websockets.remove(ws)
        return ws

    def _send_led_status(self, button, color):
        for ws in self._websockets:
            asyncio.create_task(ws.send_json({"button": button, "color": color}))

    def send_msg(self, msg: HidOutputMessage):
        future = asyncio.get_event_loop().create_future()
        if isinstance(msg, SetLed):
            color = msg.color.name.lower()
            self._led_status[msg.id] = color
            for ws in self._websockets:
                asyncio.create_task(
                    ws.send_json({"button": msg.id, "color": color})
                ).add_done_callback(lambda x: future.set_result(True))
        else:
            future.set_exception(Exception("Unsupported message type"))
        _logger.debug("Put message")
        return future

    async def process(self):
        runner = web.AppRunner(self.app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        _logger.info(f"VirtualMacropad running at http://{self.host}:{self.port}")
        print(f"VirtualMacropad running at http://{self.host}:{self.port}")


# region: Update Firmware
def check_for_device_update(device_version: VersionInfo):
    try:
        result = requests.get(
            f"https://mutenix.de/api/v1/releases/macropad-{device_version.type.name}"
        )
        if result.status_code != 200:
            _logger.error(
                "Failed to download the release info, status code: %s",
                result.status_code,
            )
            return

        releases = result.json()
        latest_version = releases.get("latest", "0.0.0")
        _logger.debug("Latest version: %s", latest_version)
        if semver.compare(device_version.version, latest_version) >= 0:
            _logger.info("Device is up to date")
            return

        print("Device update available, starting update, please be patient")
        update_url = releases.get(latest_version).get("url")
        result = requests.get(update_url)
        result.raise_for_status()
        with tempfile.TemporaryDirectory() as tmpdirname:
            with tarfile.open(fileobj=io.BytesIO(result.content), mode="r:gz") as tar:
                tar.extractall(path=tmpdirname)
        files = list(filter(lambda x: x.endswith(".py"), os.listdir(tmpdirname)))
        perform_hid_upgrade(files)
        _logger.info("Successfully updated device firmware")
    except requests.RequestException as e:
        _logger.error("Failed to check for device update availability")


HEADER_SIZE = 8
MAX_CHUNK_SIZE = 60 - HEADER_SIZE
DATA_TRANSFER_SLEEP_TIME = 0.02
STATE_CHANGE_SLEEP_TIME = 0.5


class RequestChunk:
    def __init__(self, data: bytes):
        self.parse(data)
        self.id = ""
        self.segment = 0

    def parse(self, data: bytes):
        self.identifier = data[:2].decode("utf-8")
        if self.identifier != "RQ":
            return
        self.id = int.from_bytes(data[2:4], "little")
        self.package = int.from_bytes(data[4:6], "little")
        _logger.info("Chunk request: %s", self)

    def is_valid(self):
        return self.identifier == "RQ"

    def __str__(self):
        if self.is_valid():
            return f"File: {self.id}, Package: {self.package}"
        return "Invalid Request"


class Chunk:
    @abstractmethod
    def packet(self):
        pass


class FileChunk(Chunk):
    def __init__(self, id: int, package: int, total_packages: int, content: bytes):
        self.id = id
        self.package = package
        self.total_packages = total_packages
        self.content = content

    def packet(self):
        return (
            int(2).to_bytes(2, "little")
            + self.id.to_bytes(2, "little")
            + self.total_packages.to_bytes(2, "little")
            + self.package.to_bytes(2, "little")
            + self.content
            + b"\0" * (MAX_CHUNK_SIZE - len(self.content))
        )


class FileStart(Chunk):
    def __init__(
        self, id: int, package: int, total_packages: int, filename: bytes, filesize: int
    ):
        self.id = id
        self.package = package
        self.total_packages = total_packages
        self.content = (
            bytes((len(filename),))
            + filename.encode("utf-8")
            + bytes((2,))
            + filesize.to_bytes(2, "little")
        )

    def packet(self):
        return (
            int(1).to_bytes(2, "little")
            + self.id.to_bytes(2, "little")
            + self.total_packages.to_bytes(2, "little")
            + self.package.to_bytes(2, "little")
            + self.content
            + b"\0" * (MAX_CHUNK_SIZE - len(self.content))
        )


class FileEnd(Chunk):
    def __init__(self, id: int):
        self.id = id

    def packet(self):
        return (
            int(3).to_bytes(2, "little")
            + self.id.to_bytes(2, "little")
            + b"\0" * (MAX_CHUNK_SIZE + 4)
        )


class TransferFile:
    def __init__(self, id, filename: str):
        self.id = id
        file = pathlib.Path(filename)
        self.filename = file.name
        with open(file, "rb") as f:
            self.content = f.read()
        self.size = len(self.content)
        self.packages_sent = []
        self._chunks = []
        self.make_chunks()
        _logger.debug("File %s has %s chunks", self.filename, len(self._chunks))

    def make_chunks(self):
        total_packages = self.size // MAX_CHUNK_SIZE
        self._chunks.append(
            FileStart(self.id, 0, total_packages, self.filename, self.size)
        )
        for i in range(0, self.size, MAX_CHUNK_SIZE):
            self._chunks.append(
                FileChunk(
                    self.id,
                    i // MAX_CHUNK_SIZE,
                    total_packages,
                    self.content[i : i + MAX_CHUNK_SIZE],
                )
            )
        self._chunks.append(FileEnd(self.id))

    def get_next_chunk(self) -> FileChunk:
        next = max(self.packages_sent) + 1 if len(self.packages_sent) > 0 else 0
        self.packages_sent.append(next)
        return self._chunks[next]

    @property
    def chunks(self):
        return len(self._chunks)

    def get_chunk(self, request: RequestChunk):
        if request.id != self.id:
            raise FileNotFoundError("File not found")
        if request.segment < 0 or request.segment >= len(self._chunks):
            raise ValueError("Invalid request")
        return self._chunks[request.segment + 1]

    def is_complete(self):
        return len(self.packages_sent) == len(self._chunks)


def perform_hid_upgrade(files: list[str]):
    _logger.debug("Opening device for update")
    device = hid.device()
    device.open(0x2E8A, 0x2083)
    _logger.debug("Sending prepare update")
    device.write([1, 0xE0] + [0] * 7)
    time.sleep(STATE_CHANGE_SLEEP_TIME)

    transfer_files = [TransferFile(i, file) for i, file in enumerate(files)]

    chunk_requests = []
    finished = False
    finished_at = None

    _logger.debug("Preparing to send %s files", len(transfer_files))
    file_progress_bars = {
        file.id: tqdm(
            total=file.chunks, desc=f"{file.id}/{len(transfer_files)} {file.filename}"
        )
        for file in transfer_files
    }

    while True:
        received = device.read(24, 100)
        if len(received) > 0:
            rc = RequestChunk(bytes(received))
            if rc.is_valid():
                print(rc)
                try:
                    chunk_requests.append(rc)
                except FileNotFoundError:
                    print("File not found")

        if len(chunk_requests) > 0:
            _logger.debug("Sending requested chunk")
            cr = chunk_requests.pop(0)
            file = next((f for f in transfer_files if f.id == cr.id), None)
            chunk = file.get_chunk(cr)
            device.write(bytearray((2,)) + chunk.packet())
            time.sleep(DATA_TRANSFER_SLEEP_TIME)

        try:
            file = next(filter(lambda x: not x.is_complete(), transfer_files))
            chunk = file.get_next_chunk()
            if chunk:
                _logger.debug("Sending chunk of file %s", file.filename)
                cnk = bytes((2,)) + chunk.packet()
                device.write(cnk)
                file_progress_bars[file.id].update(1)
                time.sleep(DATA_TRANSFER_SLEEP_TIME)
            else:
                print(f"File {file.filename} transfered")
        except StopIteration:
            if (finished_at and time.monotonic() - finished_at > 5) or (
                not finished_at
            ):
                break
            if not finished:
                print("All files transfered")
                finished = True
                finished_at = time.monotonic()
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    device.write([2, 4] + [0] * 59)
    time.sleep(STATE_CHANGE_SLEEP_TIME)
    print("Resetting")
    device.write([1, 0xE1] + [0] * 7)


# endregion


# region: Update Application
def check_for_self_update():
    try:
        result = requests.get("https://mutenix.de/api/v1/releases/software-python")
        if result.status_code != 200:
            _logger.error(
                "Failed to download the release info, status code: %s",
                result.status_code,
            )
            return

        versions = result.json()
        _logger.debug("Versions: %s", versions)
        latest_version = versions.get("latest", "0.0.0")
        _logger.debug("Latest version: %s", latest_version)
        if semver.compare(__version__, latest_version) >= 0:
            _logger.info("Application is up to date")
            return

        print("Application update available, starting update, please be patient")
        update_url = versions.get(latest_version).get("url")
        result = requests.get(update_url)
        result.raise_for_status()
        if result.status_code == 200:
            with tarfile.open(fileobj=io.BytesIO(result.content), mode="r:gz") as tar:
                tar.extract("macropad.py", path=pathlib.Path(__file__).parent)
                _logger.info("Successfully updated macropad.py")
        else:
            _logger.error(
                "Failed to download the update, status code: %s", result.status_code
            )

    except requests.RequestException as e:
        _logger.error("Failed to check for application update availability", e)


# endregion


async def main():
    macropad = Macropad(vid=0x2E8A, pid=0x2083)
    await macropad.process()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
