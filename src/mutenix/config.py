# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import logging
import os
from pathlib import Path

import pydantic
import yaml
from mutenix.models.config import Config

_logger = logging.getLogger(__name__)

CONFIG_FILENAME = "mutenix.yaml"


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
        config = Config()
        config._file_path = str(file_path)
        save_config(config)
        return config

    except (yaml.YAMLError, IOError) as e:
        _logger.info("Error in configuration file: %s", e)
        config = Config()
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
