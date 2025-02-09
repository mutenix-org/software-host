# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from mutenix.models.config import ActionDetails
from mutenix.models.config import ButtonAction
from mutenix.models.config import Config
from mutenix.models.config import DeviceInfo
from mutenix.models.config import Key
from mutenix.models.config import Keyboard
from mutenix.models.config import KeyTap
from mutenix.models.config import KeyType
from mutenix.models.config import LedStatus
from mutenix.models.config import LedStatusColorCommand
from mutenix.models.config import LedStatusResultCommand
from mutenix.models.config import LedStatusTeamsState
from mutenix.models.config import LoggingConfig
from mutenix.models.config import Mouse
from mutenix.models.config import MouseButton
from mutenix.models.config import MousePosition
from mutenix.models.config import VirtualMacropadConfig
from mutenix.models.config import WebhookAction
from mutenix.models.config_v0 import Config as ConfigV0
from mutenix.models.config_v0 import LedStatusSource
from mutenix.models.config_v0 import MouseActionClick
from mutenix.models.config_v0 import MouseActionMove
from mutenix.models.config_v0 import MouseActionPress
from mutenix.models.config_v0 import MouseActionRelease
from mutenix.models.config_v0 import MouseActionSetPosition


def convert_action_details(action):
    if isinstance(action, str):
        return ActionDetails(command=action)
    if isinstance(action, Key):
        return ActionDetails(keyboard=Keyboard(press=Key(key=action.key)))
    if isinstance(action, KeyTap):
        return ActionDetails(
            keyboard=Keyboard(tap=KeyTap(key=action.key, modifiers=action.modifiers)),
        )
    if isinstance(action, KeyType):
        return ActionDetails(keyboard=Keyboard(type=KeyType(string=action.string)))
    if isinstance(action, MouseActionMove):
        return ActionDetails(mouse=Mouse(move=MousePosition(x=action.x, y=action.y)))
    if isinstance(action, MouseActionSetPosition):
        return ActionDetails(mouse=Mouse(set=MousePosition(x=action.x, y=action.y)))
    if isinstance(action, MouseActionClick):
        return ActionDetails(mouse=Mouse(click=MouseButton(button=action.button)))
    if isinstance(action, MouseActionPress):
        return ActionDetails(mouse=Mouse(press=MouseButton(button=action.button)))
    if isinstance(action, MouseActionRelease):
        return ActionDetails(mouse=Mouse(release=MouseButton(button=action.button)))
    if isinstance(action, WebhookAction):
        return ActionDetails(
            webhook=WebhookAction(
                method=action.method,
                url=action.url,
                headers=action.headers,
                data=action.data,
            ),
        )
    return None


def convert_button_action(action):
    return ButtonAction(
        button_id=action.button_id,
        actions=[convert_action_details(a) for a in action.extra]
        if isinstance(action.extra, list)
        else [convert_action_details(action.extra)],
    )


def convert_led_status(led):
    if led.source == LedStatusSource.TEAMS:
        return LedStatus(
            button_id=led.button_id,
            teams_state=LedStatusTeamsState(
                teams_state=led.extra,
                color_on=led.color_on,
                color_off=led.color_off,
            ),
        )
    elif led.source == LedStatusSource.CMD:
        return LedStatus(
            button_id=led.button_id,
            result_command=LedStatusResultCommand(
                command=led.extra,
                color_on=led.color_on,
                color_off=led.color_off,
                interval=led.interval,
                timeout=led.timeout,
            ),
        )
    elif led.source == LedStatusSource.WEBHOOK:
        return LedStatus(
            button_id=led.button_id,
            color_command=LedStatusColorCommand(
                command=led.extra,
                interval=led.interval,
                timeout=led.timeout,
            ),
        )
    return None


def convert_config_v0(config: ConfigV0) -> Config:
    new_config = Config(
        version=1,
        actions=[convert_button_action(action) for action in config.actions],
        longpress_action=[
            convert_button_action(action) for action in config.longpress_action
        ],
        leds=[convert_led_status(led) for led in config.leds],
        teams_token=config.teams_token,
        virtual_keypad=VirtualMacropadConfig(
            bind_address=config.virtual_keypad.bind_address,
            bind_port=config.virtual_keypad.bind_port,
        ),
        auto_update=config.auto_update,
        device_identifications=[
            DeviceInfo(
                vendor_id=device.vendor_id,
                product_id=device.product_id,
                serial_number=device.serial_number,
            )
            for device in config.device_identifications
        ],
        logging=LoggingConfig(
            level=config.logging.level,
            submodules=config.logging.submodules,
            file_enabled=config.logging.file_enabled,
            file_path=config.logging.file_path,
            file_level=config.logging.file_level,
            file_max_size=config.logging.file_max_size,
            file_backup_count=config.logging.file_backup_count,
            console_enabled=config.logging.console_enabled,
            console_level=config.logging.console_level,
        ),
        proxy=config.proxy,
    )
    return new_config


def convert_old_config(config_data):
    if "version" not in config_data:
        return convert_config_v0(ConfigV0(**config_data))
