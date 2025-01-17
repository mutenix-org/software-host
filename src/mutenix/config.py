# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Literal
from typing import Union

import yaml
from mutenix.teams_messages import ClientMessageParameterType
from mutenix.teams_messages import MeetingAction
from pydantic import BaseModel
from pydantic import Discriminator
from pydantic import Tag

_logger = logging.getLogger(__name__)

CONFIG_FILENAME = "mutenix.yaml"


class ActionEnum(str, Enum):
    TEAMS = "teams"
    ACTIVATE_TEAMS = "activate-teams"
    CMD = "cmd"
    WEBHOOK = "webhook"
    KEYPRESS = "key-press"
    MOUSE = "mouse"


class LedStatusSource(str, Enum):
    TEAMS = "teams"
    CMD = "cmd"


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
    reaction: ClientMessageParameterType


class KeyPress(BaseModel):
    modifiers: list[str] | None = None
    key: str | None = None
    string: str | None = None


class MouseActionPosition(BaseModel):
    x: int
    y: int


class MouseActionMove(MouseActionPosition):
    action: Literal["move", None] = "move"


class MouseActionSetPosition(MouseActionPosition):
    action: Literal["set"] = "set"


class MouseActionClick(BaseModel):
    action: Literal["click"] = "click"
    button: str
    count: int = 1


class MouseActionPress(BaseModel):
    action: Literal["press"] = "press"
    button: str


class MouseActionRelease(BaseModel):
    action: Literal["release"] = "release"
    button: str


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
    method: str | None = None
    url: str
    headers: dict[str, str] | None = None
    data: dict[str, Any] | None = None


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
    button_id: int
    action: MeetingAction | ActionEnum
    extra: Annotated[
        Union[
            Annotated[None, Tag("none")],  # Teams activation and default actions
            Annotated[ClientMessageParameterType, Tag("react")],
            Annotated[SequenceType, Tag("sequence")],
            Annotated[SequenceElementType, Tag("single")],
        ],
        Discriminator(button_action_discriminator),
    ] = None


class LedStatus(BaseModel):
    button_id: int
    source: LedStatusSource
    extra: TeamsState | str | None = None
    color_on: LedColor | None = None
    color_off: LedColor | None = None
    read_result: bool = False
    interval: float = 0.0


class VirtualKeypadConfig(BaseModel):
    bind_address: str = "127.0.0.1"
    bind_port: int = 12909


class DeviceInfo(BaseModel):
    vendor_id: int | None = None
    product_id: int | None = None
    serial_number: str | None = None


class Config(BaseModel):
    actions: list[ButtonAction]
    double_tap_action: list[ButtonAction] = []
    leds: list[LedStatus] = []
    teams_token: str | None = None
    file_path: str | None = None
    virtual_keypad: VirtualKeypadConfig = VirtualKeypadConfig()
    auto_update: bool = True
    device_identifications: list[DeviceInfo] = []


def create_default_config() -> Config:
    return Config(
        actions=[
            ButtonAction(button_id=1, action=MeetingAction.ToggleMute),
            ButtonAction(button_id=2, action=MeetingAction.ToggleHand),
            ButtonAction(button_id=3, action=ActionEnum.ACTIVATE_TEAMS),
            ButtonAction(button_id=4, action=MeetingAction.React, extra="like"),
            ButtonAction(button_id=5, action=MeetingAction.LeaveCall),
            ButtonAction(button_id=6, action=MeetingAction.ToggleMute),
            ButtonAction(button_id=7, action=MeetingAction.ToggleHand),
            ButtonAction(button_id=8, action=ActionEnum.ACTIVATE_TEAMS),
            ButtonAction(button_id=9, action=MeetingAction.React, extra="like"),
            ButtonAction(button_id=10, action=MeetingAction.LeaveCall),
        ],
        double_tap_action=[
            ButtonAction(button_id=3, action=MeetingAction.ToggleVideo),
            ButtonAction(button_id=8, action=MeetingAction.ToggleVideo),
        ],
        leds=[
            LedStatus(
                button_id=1,
                source=LedStatusSource.TEAMS,
                extra=TeamsState.MUTED,
                color_on=LedColor.RED,
                color_off=LedColor.GREEN,
            ),
            LedStatus(
                button_id=2,
                source=LedStatusSource.TEAMS,
                extra=TeamsState.HAND_RAISED,
                color_on=LedColor.YELLOW,
                color_off=LedColor.BLACK,
            ),
            LedStatus(
                button_id=3,
                source=LedStatusSource.TEAMS,
                extra=TeamsState.VIDEO_ON,
                color_on=LedColor.GREEN,
                color_off=LedColor.RED,
            ),
            LedStatus(
                button_id=5,
                source=LedStatusSource.TEAMS,
                extra=TeamsState.IN_MEETING,
                color_on=LedColor.GREEN,
                color_off=LedColor.BLACK,
            ),
            LedStatus(
                button_id=6,
                source=LedStatusSource.TEAMS,
                extra=TeamsState.MUTED,
                color_on=LedColor.RED,
                color_off=LedColor.GREEN,
            ),
            LedStatus(
                button_id=7,
                source=LedStatusSource.TEAMS,
                extra=TeamsState.HAND_RAISED,
                color_on=LedColor.YELLOW,
                color_off=LedColor.BLACK,
            ),
            LedStatus(
                button_id=8,
                source=LedStatusSource.TEAMS,
                extra=TeamsState.VIDEO_ON,
                color_on=LedColor.RED,
                color_off=LedColor.GREEN,
            ),
            LedStatus(
                button_id=10,
                source=LedStatusSource.TEAMS,
                extra=TeamsState.IN_MEETING,
                color_on=LedColor.GREEN,
                color_off=LedColor.BLACK,
            ),
        ],
        teams_token=None,
        virtual_keypad=VirtualKeypadConfig(bind_address="127.0.0.1", bind_port=12909),
    )


def find_config_file() -> Path:
    file_path = Path(CONFIG_FILENAME)
    home_config_path = (
        Path.home() / os.environ.get("XDG_CONFIG_HOME", ".config") / CONFIG_FILENAME
    )

    if not file_path.exists() and home_config_path.exists():
        file_path = home_config_path

    return file_path


def load_config(file_path: Path | None = None) -> Config:
    if file_path is None:
        file_path = find_config_file()

    try:
        _logger.info("Loading config from file: %s", file_path)
        with open(file_path, "r") as file:
            config_data = yaml.safe_load(file)
        if config_data is None:
            raise yaml.YAMLError("No data in file")
    except (FileNotFoundError, yaml.YAMLError, IOError) as e:
        print(e)

        config = create_default_config()
        config.file_path = str(file_path)
        save_config(config)
        return config

    config_data["file_path"] = str(file_path)
    return Config(**config_data)


def save_config(config: Config, file_path: Path | str | None = None):
    if file_path is None:
        if config.file_path is None:
            raise ValueError("No file path provided")  # pragma: no cover

        file_path = config.file_path

    config.file_path = None
    try:
        with open(file_path, "w") as file:
            yaml.dump(config.model_dump(mode="json"), file)
    except (FileNotFoundError, yaml.YAMLError, IOError):
        _logger.error("Failed to write config to file: %s", file_path)
