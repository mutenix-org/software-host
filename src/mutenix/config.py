# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import json
import logging
import os
from abc import ABC
from enum import Enum
from pathlib import Path
from typing import Any
from typing import ClassVar

import pydantic
import yaml
from mutenix.teams_messages import ClientMessageParameterType
from mutenix.teams_messages import MeetingAction
from pydantic import BaseModel
from pydantic import Field

_logger = logging.getLogger(__name__)

CONFIG_FILENAME = "mutenix.yaml"


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
    key: str | None = Field(
        default=None,
        description="The key to be pressed. This field has precedence over 'string'.",
        examples=["a", "F1", "Enter"],
    )
    modifiers: list[str] | None = Field(
        default=None,
        description="List of modifier keys to be held down during the key press.",
        examples=[["ctrl", "shift"], ["alt"]],
    )


class KeyType(BaseModel):
    string: str | None = Field(
        default=None,
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
    parameters: dict[str, Any] | None = Field(
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

    OPTION_FIELDS: ClassVar[list[str]] = [
        "webhook",
        "keyboard",
        "mouse",
        "teams_reaction",
        "meeting_action",
        "activate_teams",
        "command",
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


class VirtualKeypadConfig(BaseModel):
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


class Config(BaseModel):
    """
    Mutenix configuration parameters for actions, leds keypad and more.
    """

    _internal_state: Any = pydantic.PrivateAttr()
    _file_path: str = pydantic.PrivateAttr(default=None)
    actions: list[ButtonAction] = [ButtonAction(button_id=i) for i in range(1, 11)]
    longpress_action: list[ButtonAction] = pydantic.Field(
        default_factory=lambda: [ButtonAction(button_id=i) for i in range(1, 11)],
        validation_alias=pydantic.AliasChoices("longpress_action", "double_tap_action"),
    )
    leds: list[LedStatus] = [LedStatus(button_id=i, off=True) for i in range(1, 11)]
    teams_token: str | None = None
    virtual_keypad: VirtualKeypadConfig = VirtualKeypadConfig()
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


def create_default_config() -> Config:
    config = Config(
        actions=[
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
        ],
        longpress_action=[
            ButtonAction(
                button_id=3,
                actions=[ActionDetails(meeting_action=MeetingAction.ToggleVideo)],
            ),
            ButtonAction(
                button_id=8,
                actions=[ActionDetails(meeting_action=MeetingAction.ToggleVideo)],
            ),
        ],
        leds=[
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
        ],
        teams_token=None,
        virtual_keypad=VirtualKeypadConfig(
            bind_address="127.0.0.1",
            bind_port=12909,
        ),
    )
    config._internal_state = "default"
    return config


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
    except FileNotFoundError:
        _logger.info("No config file found, creating default one")
        config = create_default_config()
        config._file_path = str(file_path)
        save_config(config)
        return config

    except (yaml.YAMLError, IOError) as e:
        _logger.info("Error in configuration file: %s", e)
        config = create_default_config()
        config._internal_state = "default_fallback"
        config._file_path = str(file_path)
        return config

    except pydantic.ValidationError as e:
        _logger.info("Configuration errors:")
        for error in e.errors():
            _logger.info(error)

    config_data["_file_path"] = str(file_path)
    return Config(**config_data)


def save_config(config: Config, file_path: Path | str | None = None):
    if file_path is None:
        if config._file_path is None:
            config._file_path = str(find_config_file())
        file_path = config._file_path
    else:
        config._file_path = file_path  # type: ignore

    if config._internal_state == "default_fallback":
        _logger.error("Not saving default config")
        return
    try:
        file_path = Path(config._file_path)
        with file_path.open("w") as file:
            yaml.dump(
                config.model_dump(mode="json", exclude_none=True, exclude_unset=True),
                file,
            )
            file.write(
                "\n# yaml-language-server: $schema=https://github.com/mutenix-org/software-host/raw/refs/heads/main/docs/mutenix.schema.json\n",
            )
    except (FileNotFoundError, yaml.YAMLError, IOError):
        _logger.error("Failed to write config to file: %s", file_path)


if __name__ == "__main__":
    print(json.dumps(Config.model_json_schema()))

    # config = load_config()
    # print(config.model_dump_json(indent=2))

    # print(generate_example_config_markdown())
