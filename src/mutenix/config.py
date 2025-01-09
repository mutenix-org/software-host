from __future__ import annotations

import logging
import os
from enum import Enum
from pathlib import Path
from typing import List

import yaml
from mutenix.teams_messages import MeetingAction
from pydantic import BaseModel

_logger = logging.getLogger(__name__)

CONFIG_FILENAME = "mutenix.yaml"


class ActionEnum(str, Enum):
    ACTIVATE_TEAMS = "activate-teams"
    CMD = "cmd"


class ButtonAction(BaseModel):
    button_id: int
    action: MeetingAction | ActionEnum
    extra: str | None = None


class Config(BaseModel):
    actions: List[ButtonAction]
    double_tap_action: List[ButtonAction] = []
    teams_token: str | None = None
    file_path: str | None = None


def create_default_config() -> Config:
    return Config(
        actions=[
            ButtonAction(button_id=1, action=MeetingAction.ToggleMute),
            ButtonAction(button_id=2, action=MeetingAction.ToggleHand),
            ButtonAction(button_id=3, action=ActionEnum.ACTIVATE_TEAMS),
            ButtonAction(button_id=4, action=MeetingAction.React, extra="like"),
            ButtonAction(button_id=5, action=MeetingAction.LeaveCall),
        ],
        double_tap_action=[
            ButtonAction(button_id=3, action=MeetingAction.ToggleVideo),
        ],
        teams_token=None,
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
        with open(file_path, "r") as file:
            config_data = yaml.safe_load(file)
    except (FileNotFoundError, yaml.YAMLError, IOError):
        config = create_default_config()
        config.file_path = str(file_path)
        save_config(config)
        return config

    return Config(**config_data, file_path=str(file_path))


def save_config(config: Config, file_path: Path | str | None = None):
    if file_path is None:
        if config.file_path is None:
            raise ValueError("No file path provided")

        file_path = config.file_path

    config.file_path = None
    try:
        with open(file_path, "w") as file:
            yaml.dump(config.model_dump(), file)
    except (FileNotFoundError, yaml.YAMLError, IOError):
        _logger.error("Failed to write config to file: %s", file_path)
