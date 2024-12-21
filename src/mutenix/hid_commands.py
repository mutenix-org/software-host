from abc import ABC, abstractmethod
from enum import IntEnum, ReprEnum
from typing import override

class HardwareTypes(IntEnum):
    """Hardware types for the Macropad."""
    UNKNOWN = 0x00
    SINGLE_BUTTON = 0x01
    FIVE_BUTTON_USB = 0x02
    FIVE_BUTTON_BT = 0x03
    TEN_BUTTON_USB = 0x04
    TEN_BUTTON_BT = 0x05

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