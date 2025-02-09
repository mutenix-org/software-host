# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import logging
from enum import Enum
from typing import Annotated
from typing import Any
from typing import Literal
from typing import Union

import pydantic
from mutenix.models.teams_messages import ClientMessageParameterType
from mutenix.models.teams_messages import MeetingAction
from pydantic import BaseModel
from pydantic import Discriminator
from pydantic import Field
from pydantic import Tag

_logger = logging.getLogger(__name__)


class ActionEnum(str, Enum):
    """
    ActionEnum is an enumeration that represents different types of actions that can be performed.
    """

    TEAMS = "teams"
    ACTIVATE_TEAMS = "activate-teams"
    CMD = "cmd"
    WEBHOOK = "webhook"
    KEYPRESS = "key-press"
    MOUSE = "mouse"


class LedStatusSource(str, Enum):
    TEAMS = "teams"
    CMD = "cmd"
    WEBHOOK = "webhook"


class LedColor(str, Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    WHITE = "white"
    BLACK = "black"
    YELLOW = "yellow"
    CYAN = "cyan"
    MAGENTA = "magenta"
    ORANGE = "orange"
    PURPLE = "purple"


class TeamsState(str, Enum):
    MUTED = "is-muted"
    HAND_RAISED = "is-hand-raised"
    IN_MEETING = "is-in-meeting"
    RECORDING_ON = "is-recording-on"
    BACKGROUND_BLURRED = "is-background-blurred"
    SHARING = "is-sharing"
    UNREAD_MESSAGES = "has-unread-messages"
    VIDEO_ON = "is-video-on"


class TeamsReact(str, Enum):
    reaction: ClientMessageParameterType = Field(
        description="The type of client message parameter for the reaction.",
    )


class KeyPress(BaseModel):
    key: str | None = Field(default=None, description="The key to be pressed.")
    string: str | None = Field(default=None, description="The string to be typed.")
    modifiers: list[str] | None = Field(
        default=None,
        description="List of modifier keys to be held down during the key press.",
    )


class MouseActionPosition(BaseModel):
    x: int = Field(description="The x-coordinate of the mouse action position.")
    y: int = Field(description="The y-coordinate of the mouse action position.")


class MouseActionMove(MouseActionPosition):
    action: Literal["move", None] = Field(
        default="move",
        description="The action type for moving the mouse.",
    )


class MouseActionSetPosition(MouseActionPosition):
    action: Literal["set"] = Field(
        default="set",
        description="The action type for setting the mouse position.",
    )


class MouseActionClick(BaseModel):
    action: Literal["click"] = Field(
        default="click",
        description="The action type for clicking the mouse.",
    )
    button: str = Field(description="The mouse button to be clicked.")
    count: int = Field(
        default=1,
        description="The number of times the mouse button should be clicked.",
    )


class MouseActionPress(BaseModel):
    action: Literal["press"] = Field(
        default="press",
        description="The action type for pressing the mouse button.",
    )
    button: str = Field(description="The mouse button to be pressed.")


class MouseActionRelease(BaseModel):
    action: Literal["release"] = Field(
        default="release",
        description="The action type for releasing the mouse button.",
    )
    button: str = Field(description="The mouse button to be released.")


MouseMove = Annotated[
    Union[
        Annotated[MouseActionMove, Tag("move")],
        Annotated[MouseActionSetPosition, Tag("set")],
        Annotated[MouseActionClick, Tag("click")],
        Annotated[MouseActionPress, Tag("press")],
        Annotated[MouseActionRelease, Tag("release")],
    ],
    Discriminator(lambda v: v["action"] if "action" in v else "move"),
]


class WebhookAction(BaseModel):
    method: str = Field(
        default="GET",
        description="The HTTP method to use for the webhook action.",
    )
    url: str = Field(..., description="The URL to send the webhook request to.")
    headers: dict[str, str] = Field(
        default={},
        description="Optional headers to include in the webhook request.",
    )
    data: dict[str, Any] | None = Field(
        default=None,
        description="Optional data to include in the webhook request.",
    )


def button_action_details_descriminator(v: Any) -> str:
    if isinstance(v, str):
        return "cmd"
    if not isinstance(v, dict):
        return ""
    if "key" in v or "modifiers" in v or "string" in v:
        return "key"
    if "x" in v or "y" in v or "button" in v:
        return "mouse"
    if "url" in v:
        return "webhook"
    return ""


SequenceElementType = Annotated[
    Union[
        Annotated[KeyPress, Tag("key")],
        Annotated[MouseMove, Tag("mouse")],
        Annotated[str, Tag("cmd")],
        Annotated[WebhookAction, Tag("webhook")],
    ],
    Discriminator(button_action_details_descriminator),
]

SequenceType = list[SequenceElementType]


def button_action_discriminator(v: Any) -> str:
    if v is None:
        return "none"
    if isinstance(v, str):
        if str(v).lower() in [e.value for e in ClientMessageParameterType]:
            return "react"
    if isinstance(v, (list)):
        return "sequence"
    if isinstance(v, (dict)):
        return "single"
    return "none"


class ButtonAction(BaseModel):
    button_id: int = Field(
        ...,
        ge=1,
        le=10,
        description="The ID of the button, must be between 1 and 10 inclusive.",
    )
    action: Union[MeetingAction, ActionEnum] = Field(
        description="The action associated with the button.",
    )
    extra: Annotated[
        Union[
            Annotated[None, Tag("none")],
            Annotated[ClientMessageParameterType, Tag("react")],
            Annotated[SequenceType, Tag("sequence")],
            Annotated[SequenceElementType, Tag("single")],
        ],
        Discriminator(button_action_discriminator),
    ] = Field(
        default=None,
        description="Additional parameters for the action, can be None, a client message parameter, a sequence, or a single sequence element.",
    )


class LedStatus(BaseModel):
    button_id: int = Field(
        ...,
        ge=1,
        le=10,
        description="The ID of the button, must be between 1 and 10.",
    )
    source: LedStatusSource = Field(description="The source of the LED status.")
    extra: TeamsState | str | None = Field(
        default=None,
        description="Additional information about the LED status, can be a TeamsState, string, or None.",
    )
    color_on: LedColor | None = Field(
        default=None,
        description="The color of the LED when it is on.",
    )
    color_off: LedColor | None = Field(
        default=None,
        description="The color of the LED when it is off.",
    )
    read_result: bool = Field(
        default=False,
        description="Indicates whether the result has been read.",
    )
    interval: float = Field(
        default=5.0,
        description="The interval to run the command in, default is 5.0 seconds.",
    )
    timeout: float = Field(
        default=0.5,
        description="Maximum allowed runtime for the command, color will be set to 'black' if timeout occurs, default is 0.5 seconds.",
    )


class VirtualKeypadConfig(BaseModel):
    bind_address: str = Field(
        default="127.0.0.1",
        description="The IP address to bind the virtual keypad server to. Defaults to '127.0.0.1'.",
    )
    bind_port: int = Field(
        default=12909,
        description="The port number to bind the virtual keypad server to. Defaults to 12909.",
    )


class DeviceInfo(BaseModel):
    vendor_id: int | None = Field(
        default=None,
        description="The vendor ID of the device.",
        ge=0,
        lt=2**24,
    )
    product_id: int | None = Field(
        default=None,
        description="The product ID of the device.",
        ge=0,
        lt=2**16,
    )
    serial_number: str | None = Field(
        default=None,
        description="The serial number of the device.",
    )


class LoggingConfig(BaseModel):
    class LogLevel(str, Enum):
        DEBUG = "debug"
        INFO = "info"
        WARNING = "warning"
        ERROR = "error"
        CRITICAL = "critical"

        def to_logging_level(self) -> int:
            return getattr(logging, self.name)

    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="The logging level for the application.",
    )
    submodules: list[str] = Field(
        default_factory=list,
        description="List of submodules to apply specific logging configurations.",
    )
    file_enabled: bool = Field(
        default=True,
        description="Flag to enable or disable logging to a file.",
    )
    file_path: str | None = Field(
        default=None,
        description="The file path for the log file.",
    )
    file_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="The logging level for the log file.",
    )
    file_max_size: int = Field(
        default=3_145_728,
        description="The maximum size of the log file in bytes before it is rotated.",
    )
    file_backup_count: int = Field(
        default=5,
        description="The number of backup log files to keep.",
    )
    console_enabled: bool = Field(
        default=False,
        description="Flag to enable or disable logging to the console.",
    )
    console_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="The logging level for the console output.",
    )


class Config(BaseModel):
    _internal_state: Any = pydantic.PrivateAttr()
    version: int = Field(default=0)
    actions: list[ButtonAction]
    longpress_action: list[ButtonAction] = pydantic.Field(
        validation_alias=pydantic.AliasChoices("longpress_action", "double_tap_action"),
    )
    leds: list[LedStatus] = []
    teams_token: str | None = None
    file_path: str | None = None
    virtual_keypad: VirtualKeypadConfig = VirtualKeypadConfig()
    auto_update: bool = True
    device_identifications: list[DeviceInfo] = [
        DeviceInfo(vendor_id=0x1D50, product_id=0x6189, serial_number=None),
        DeviceInfo(vendor_id=7504, product_id=24774, serial_number=None),
        DeviceInfo(vendor_id=4617, product_id=1, serial_number=None),
    ]
    logging: LoggingConfig = LoggingConfig()
    proxy: str | None = None
