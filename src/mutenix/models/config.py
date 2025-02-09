# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import logging
from abc import ABC
from enum import Enum
from typing import Any
from typing import ClassVar

import pydantic
from mutenix.models.teams_messages import ClientMessageParameterType
from mutenix.models.teams_messages import MeetingAction
from pydantic import BaseModel
from pydantic import Field


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


class AtLeastOneOption(ABC):
    OPTION_FIELDS: ClassVar[list[str]] = []

    @pydantic.model_validator(mode="before")
    def at_least_one_option(cls, values):
        option_fields = cls.OPTION_FIELDS
        if not any(values.get(field) for field in option_fields):
            raise ValueError(
                f"At least one of the following fields must be set: {', '.join(option_fields)}",
            )
        return values


class TeamsReact(BaseModel):
    reaction: ClientMessageParameterType = Field(
        description="The type of client message parameter for the reaction.",
    )


class Key(BaseModel):
    key: str | None = Field(
        default=None,
        description="The key to be pressed. This field has precedence over 'string'.",
        examples=["a", "F1", "Enter"],
    )


class KeyTap(BaseModel):
    key: str = Field(
        default=None,
        description="The key to be pressed. This field has precedence over 'string'.",
        examples=["a", "F1", "Enter"],
    )
    modifiers: list[str] = Field(
        default_factory=list,
        description="List of modifier keys to be held down during the key press.",
        examples=[["ctrl", "shift"], ["alt"]],
    )


class KeyType(BaseModel):
    string: str = Field(
        description="The string to be typed. This field is only used if 'key' is not set.",
        examples=["Hello", "World"],
    )


class Keyboard(BaseModel, AtLeastOneOption):
    press: Key | None = Field(
        default=None,
        description="The key press action to be performed. This will hold down the key until released.",
    )
    release: Key | None = Field(
        default=None,
        description="The key release action to be performed. This will release the key.",
    )
    tap: KeyTap | None = Field(
        default=None,
        description="The key tap action to be performed. This will press and release the key.",
    )
    type: KeyType | None = Field(
        default=None,
        description="The key type action to be performed. This will type the string.",
    )

    OPTION_FIELDS: ClassVar[list[str]] = ["press", "release", "tap", "type"]


class MousePosition(BaseModel):
    x: int = Field(
        description="The x-coordinate of the mouse action position.",
        examples=[0, 100],
    )
    y: int = Field(
        description="The y-coordinate of the mouse action position.",
        examples=[0, 100],
    )


class MouseButton(BaseModel):
    button: str = Field(
        description="The mouse button to be clicked.",
        examples=["left", "right"],
    )


class Mouse(BaseModel, AtLeastOneOption):
    move: MousePosition | None = Field(
        default=None,
        description="The mouse move action to be performed.",
    )
    set: MousePosition | None = Field(
        default=None,
        description="The mouse set position action to be performed.",
    )
    click: MouseButton | None = Field(
        default=None,
        description="The mouse click action to be performed.",
    )
    press: MouseButton | None = Field(
        default=None,
        description="The mouse press action to be performed.",
    )
    release: MouseButton | None = Field(
        default=None,
        description="The mouse release action to be performed.",
    )
    OPTION_FIELDS: ClassVar[list[str]] = ["move", "set", "click", "press", "release"]


class DelayAction(BaseModel):
    delay: float = Field(
        ...,
        ge=0.0,
        description="The delay in seconds before the action is performed.",
        examples=[0.5, 1.0],
    )


class WebhookAction(BaseModel):
    method: str = Field(
        default="GET",
        description="The HTTP method to use for the webhook action.",
        examples=["GET", "POST"],
    )
    url: str = Field(..., description="The URL to send the webhook request to.")
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Optional headers to include in the webhook request.",
        examples=[{"Content-Type": "application/json"}],
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Optional parameters to include as url params in the web request.",
        examples=[{"key": "value"}],
    )
    data: dict[str, Any] | None = Field(
        default=None,
        description="Optional data to include in the webhook request.",
        examples=[{"key": "value"}],
    )


class ActionDetails(BaseModel, AtLeastOneOption):
    webhook: WebhookAction | None = Field(
        default=None,
        description="The webhook action to be performed.",
    )
    keyboard: Keyboard | None = Field(
        default=None,
        description="The key press action to be performed.",
    )
    mouse: Mouse | None = Field(
        default=None,
        description="The mouse action to be performed.",
    )
    teams_reaction: TeamsReact | None = Field(
        default=None,
        description="The Teams reaction to be performed.",
    )
    meeting_action: MeetingAction | None = Field(
        default=None,
        description="The meeting action to be performed.",
    )
    activate_teams: bool = Field(
        default=False,
        description="Flag to activate Teams.",
    )
    command: str | None = Field(
        default=None,
        description="The command to be executed.",
    )
    delay: DelayAction | None = Field(
        default=None,
        description="The delay in seconds to wait. Be carefully with this option.",
    )

    OPTION_FIELDS: ClassVar[list[str]] = [
        "webhook",
        "keyboard",
        "mouse",
        "teams_reaction",
        "meeting_action",
        "activate_teams",
        "command",
        "delay",
    ]


class ButtonAction(BaseModel):
    button_id: int = Field(
        ...,
        ge=1,
        le=10,
        description="The ID of the button, must be between 1 and 10 inclusive.",
        examples=[1, 2, 3],
    )
    actions: list[ActionDetails] = Field(
        default_factory=list,
        description="The actions to be performed when the button is pressed.",
        examples=[
            """
                    "webhook": {
                        "method": "POST",
                        "url": "https://example.com/webhook",
                        "headers": {"Content-Type": "application/json"},
                        "parameters": {"key": "value"},
                        "data": {"key": "value"},
                    }
            """,
            """
                    "keyboard": {
                        "press": {"key": "a"},
                    },
            """,
            """
                    "mouse": {
                        "set": {"x": 300, "y": 400},
                    },
            """,
            """
                    "teams_reaction": {"reaction": "like"}
            """,
            """
                    "meeting_action": "toggle-mute"
            """,
            """
                    "activate_teams": True
            """,
            """
                    "command": "echo 'Hello World'"
            """,
        ],
    )


class LedStatusColoredCheck(BaseModel):
    color_on: LedColor = Field(
        default=LedColor.GREEN,
        description="The color of the LED when result is `0` or the value is true",
        examples=["green", "red"],
    )
    color_off: LedColor = Field(
        default=LedColor.RED,
        description="The color of the LED when result is not `0` or the value is false.",
        examples=["green", "red"],
    )


class LedStatusColorCommand(BaseModel):
    command: str = Field(
        ...,
        description="The command to be executed. It must output a color name.",
        examples=["echo green", "echo red"],
    )
    interval: float = Field(
        default=5.0,
        description="The interval to run the command in, default is 5.0 seconds.",
        examples=[5.0, 15.0],
    )
    timeout: float = Field(
        default=0.5,
        description="Maximum allowed runtime for the command, color will be set to 'black' if timeout occurs, default is 0.5 seconds.",
        examples=[0.5, 1.0],
    )


class LedStatusResultCommand(LedStatusColorCommand, LedStatusColoredCheck):
    pass


class LedStatusTeamsState(LedStatusColoredCheck):
    teams_state: TeamsState = Field(
        ...,
        description="The Teams state to be used for the LED status.",
        examples=["is-muted", "is-hand-raised"],
    )


class LedStatus(BaseModel, AtLeastOneOption):
    button_id: int = Field(
        ...,
        ge=1,
        le=10,
        description="The ID of the button, must be between 1 and 10.",
        examples=[1, 2, 3],
    )
    teams_state: LedStatusTeamsState | None = Field(
        default=None,
        description="The Teams state to be used for the LED status.",
    )
    result_command: LedStatusResultCommand | None = Field(
        default=None,
        description="The command to be used for the LED status. (on/off)",
    )
    color_command: LedStatusColorCommand | None = Field(
        default=None,
        description="The command to be used for the LED status. (color)",
    )
    webhook: bool = Field(
        default=False,
        description="Flag to enable the color via webhook.",
    )
    off: bool = Field(
        default=False,
        description="Flag to disable the LED.",
    )

    OPTION_FIELDS: ClassVar[list[str]] = [
        "teams_state",
        "result_command",
        "color_command",
        "webhook",
        "off",
    ]


class VirtualMacropadConfig(BaseModel):
    bind_address: str = Field(
        default="127.0.0.1",
        description="The IP address to bind the virtual keypad server to. Defaults to '127.0.0.1'.",
        examples=["0.0.0.0"],
    )
    bind_port: int = Field(
        default=12909,
        description="The port number to bind the virtual keypad server to. Defaults to 12909.",
        le=65535,
        ge=1024,
        examples=[12909, 8080],
    )


class DeviceInfo(BaseModel):
    vendor_id: int | None = Field(
        default=None,
        description="The vendor ID of the device.",
        ge=0,
        lt=2**24,
        examples=[0x1D50, 0x4617],
    )
    product_id: int | None = Field(
        default=None,
        description="The product ID of the device.",
        ge=0,
        lt=2**16,
        examples=[0x6189, 0x1],
    )
    serial_number: str | None = Field(
        default=None,
        description="The serial number of the device.",
        examples=["123456", "ABCDEF"],
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
        examples=["debug", "info"],
    )
    submodules: list[str] = Field(
        default_factory=list,
        description="List of submodules to apply specific logging configurations.",
        examples=["mutenix.hid_device=debug", "mutenix.macropad=info"],
    )
    file_enabled: bool = Field(
        default=True,
        description="Flag to enable or disable logging to a file.",
    )
    file_path: str | None = Field(
        default=None,
        description="The file path for the log file.",
        examples=["/var/log/mutenix.log"],
    )
    file_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="The logging level for the log file.",
        examples=["debug", "info"],
    )
    file_max_size: int = Field(
        default=3_145_728,
        description="The maximum size of the log file in bytes before it is rotated.",
        examples=[3_145_728, 10_485_760],
    )
    file_backup_count: int = Field(
        default=5,
        description="The number of backup log files to keep.",
        examples=[0, 5, 10],
    )
    console_enabled: bool = Field(
        default=False,
        description="Flag to enable or disable logging to the console.",
    )
    console_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="The logging level for the console output.",
        examples=["debug", "info"],
    )


def _default_actions():
    return [
        ButtonAction(
            button_id=1,
            actions=[ActionDetails(meeting_action=MeetingAction.ToggleMute)],
        ),
        ButtonAction(
            button_id=2,
            actions=[ActionDetails(meeting_action=MeetingAction.ToggleHand)],
        ),
        ButtonAction(
            button_id=3,
            actions=[ActionDetails(activate_teams=True)],
        ),
        ButtonAction(
            button_id=4,
            actions=[
                ActionDetails(
                    teams_reaction=TeamsReact(
                        reaction=ClientMessageParameterType.ReactLike,
                    ),
                ),
            ],
        ),
        ButtonAction(
            button_id=5,
            actions=[ActionDetails(meeting_action=MeetingAction.LeaveCall)],
        ),
        ButtonAction(
            button_id=6,
            actions=[ActionDetails(meeting_action=MeetingAction.ToggleMute)],
        ),
        ButtonAction(
            button_id=7,
            actions=[ActionDetails(meeting_action=MeetingAction.ToggleHand)],
        ),
        ButtonAction(button_id=8, actions=[ActionDetails(activate_teams=True)]),
        ButtonAction(
            button_id=9,
            actions=[
                ActionDetails(
                    teams_reaction=TeamsReact(
                        reaction=ClientMessageParameterType.ReactLike,
                    ),
                ),
            ],
        ),
        ButtonAction(
            button_id=10,
            actions=[ActionDetails(meeting_action=MeetingAction.LeaveCall)],
        ),
    ]


def _default_longpress():
    return [
        ButtonAction(
            button_id=3,
            actions=[ActionDetails(meeting_action=MeetingAction.ToggleVideo)],
        ),
        ButtonAction(
            button_id=8,
            actions=[ActionDetails(meeting_action=MeetingAction.ToggleVideo)],
        ),
    ]


def _default_leds():
    return [
        LedStatus(
            button_id=1,
            teams_state=LedStatusTeamsState(
                teams_state=TeamsState.MUTED,
                color_off=LedColor.RED,
                color_on=LedColor.GREEN,
            ),
        ),
        LedStatus(
            button_id=2,
            teams_state=LedStatusTeamsState(
                teams_state=TeamsState.HAND_RAISED,
                color_on=LedColor.YELLOW,
                color_off=LedColor.BLACK,
            ),
        ),
        LedStatus(
            button_id=3,
            teams_state=LedStatusTeamsState(
                teams_state=TeamsState.VIDEO_ON,
                color_on=LedColor.GREEN,
                color_off=LedColor.RED,
            ),
        ),
        LedStatus(
            button_id=5,
            teams_state=LedStatusTeamsState(
                teams_state=TeamsState.IN_MEETING,
                color_on=LedColor.GREEN,
                color_off=LedColor.BLACK,
            ),
        ),
        LedStatus(
            button_id=6,
            teams_state=LedStatusTeamsState(
                teams_state=TeamsState.MUTED,
                color_on=LedColor.RED,
                color_off=LedColor.GREEN,
            ),
        ),
        LedStatus(
            button_id=7,
            teams_state=LedStatusTeamsState(
                teams_state=TeamsState.HAND_RAISED,
                color_on=LedColor.YELLOW,
                color_off=LedColor.BLACK,
            ),
        ),
        LedStatus(
            button_id=8,
            teams_state=LedStatusTeamsState(
                teams_state=TeamsState.VIDEO_ON,
                color_on=LedColor.RED,
                color_off=LedColor.GREEN,
            ),
        ),
        LedStatus(
            button_id=10,
            teams_state=LedStatusTeamsState(
                teams_state=TeamsState.IN_MEETING,
                color_on=LedColor.GREEN,
                color_off=LedColor.BLACK,
            ),
        ),
    ]


class Config(BaseModel):
    """
    Mutenix configuration parameters for actions, leds keypad and more.
    """

    _internal_state: Any = pydantic.PrivateAttr(default="default")
    _file_path: str = pydantic.PrivateAttr(default=None)
    actions: list[ButtonAction] = Field(default_factory=_default_actions)
    longpress_action: list[ButtonAction] = pydantic.Field(
        default_factory=_default_longpress,
        validation_alias=pydantic.AliasChoices("longpress_action", "double_tap_action"),
    )
    leds: list[LedStatus] = Field(default_factory=_default_leds)
    teams_token: str | None = None
    virtual_keypad: VirtualMacropadConfig = VirtualMacropadConfig()
    auto_update: bool = True
    device_identifications: list[DeviceInfo] = [
        DeviceInfo(vendor_id=0x1D50, product_id=0x6189, serial_number=None),
        DeviceInfo(vendor_id=7504, product_id=24774, serial_number=None),
        DeviceInfo(vendor_id=4617, product_id=1, serial_number=None),
    ]
    logging: LoggingConfig = LoggingConfig()
    proxy: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_unique_button_ids(cls, values):
        button_ids = [action.button_id for action in values.actions]
        if len(button_ids) != len(set(button_ids)):
            raise ValueError("All button_ids must be unique.")
        button_ids = [led.button_id for led in values.leds]
        if len(button_ids) != len(set(button_ids)):
            raise ValueError("All button_ids must be unique.")
        return values
