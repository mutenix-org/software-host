# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
from abc import ABC
from abc import abstractmethod
from enum import IntEnum
from enum import ReprEnum
from typing import override


class HardwareTypes(IntEnum):
    """Hardware types for the Macropad."""

    UNKNOWN = 0x00
    SINGLE_BUTTON = 0x02
    FIVE_BUTTON_USB = 0x03
    FIVE_BUTTON_BT = 0x04
    TEN_BUTTON_USB = 0x05
    TEN_BUTTON_BT = 0x06


class HidInCommands(IntEnum):
    """Identifiers for incoming HID messages."""

    VERSION_INFO = 0x99
    STATUS = 0x1
    STATUS_REQUEST = 0x2


class HidOutCommands(IntEnum):
    """Identifiers for outgoing HID messages."""

    SET_LED = 0x1
    PING = 0xF0
    PREPARE_UPDATE = 0xE0
    RESET = 0xE1
    UPDATE_CONFIG = 0xE2


class HidInputMessage:
    MESSAGE_LENGTH = 8

    @staticmethod
    def from_buffer(buffer: bytes):
        match buffer[1]:
            case HidInCommands.VERSION_INFO:
                return VersionInfo(buffer[2:8])
            case HidInCommands.STATUS:
                return Status(buffer[2:8])
            case HidInCommands.STATUS_REQUEST.value:
                return StatusRequest()
        raise NotImplementedError

    def __repr__(self):  # pragma: no cover
        return self.__str__()


class Status(HidInputMessage):
    @classmethod
    def trigger_button(cls, button: int):
        return cls(bytes([button, 1, 0, 0, 1]))

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


class StatusRequest(HidInputMessage):
    def __str__(self):  # pragma: no cover
        return "Status Request"


class HidOutputMessage:
    REPORT_ID = 1
    pass


class HidCommand(HidOutputMessage, ABC):
    REPORT_ID = 1
    _counter = 0

    def __init__(self):
        type(self)._counter = (type(self)._counter + 1) % 256
        self._current_counter = type(self)._counter

    @abstractmethod
    def to_buffer(self) -> bytes:  # pragma: no cover
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
        super().__init__()
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
                self._current_counter,
            ],
        )

    def __eq__(self, other):
        return self.id == other.id and self.color == other.color

    def __str__(self):
        return f"SetLed {{ id: {self.id}, color: {self.color.name} }}"


class UpdateConfig(HidCommand):
    def __init__(self):
        super().__init__()
        self._activate_debug = 0
        self._activate_filesystem = 0

    def activate_debug(self, activate: bool):
        self._activate_debug = 2 if activate else 1

    def activate_filesystem(self, activate: bool):
        self._activate_filesystem = 2 if activate else 1

    @override
    def to_buffer(self) -> bytes:
        return bytes(
            [
                HidOutCommands.UPDATE_CONFIG,
                self._activate_debug,
                self._activate_filesystem,
                0,
                0,
                0,
                0,
                self._current_counter,
            ],
        )

    def __str__(self):
        return f"UpdateConfig {{ debug: {self.activate_debug}, filesystem: {self.activate_filesystem} }}"


class SimpleHidCommand(HidCommand):
    def __init__(self, command: HidOutCommands):
        super().__init__()
        self.command = command

    @override
    def to_buffer(self) -> bytes:
        return bytes([int(self.command), 0, 0, 0, 0, 0, 0, self._current_counter])

    def __str__(self):  # pragma: no cover
        return f"{self.command.name}"

    def __repr__(self):  # pragma: no cover
        return self.__str__()


class Ping(SimpleHidCommand):
    def __init__(self):
        super().__init__(HidOutCommands.PING)


class PrepareUpdate(SimpleHidCommand):
    def __init__(self):
        super().__init__(HidOutCommands.PREPARE_UPDATE)


class Reset(SimpleHidCommand):
    def __init__(self):
        super().__init__(HidOutCommands.RESET)
