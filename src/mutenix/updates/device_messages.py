import logging

_logger = logging.getLogger(__name__)


class UpdateError:
    def __init__(self, data: bytes):
        self.info = ""
        self.parse(data)

    def parse(self, data: bytes):
        self.identifier = data[:2].decode("utf-8")
        if not self.is_valid:
            return
        length = max(int.from_bytes(data[2:3], "little"), 33)
        self.info = data[3 : 3 + length].decode("utf-8")
        _logger.info("Error received: %s", self)

    @property
    def is_valid(self):
        return self.identifier == "ER"

    def __str__(self):
        if self.is_valid:
            return f"Error: {self.info}"
        return "Invalid Request"


class ChunkAck:
    def __init__(self, data: bytes):
        self.id = 0
        self.package = 0
        self.type_ = 0
        self.parse(data)

    def parse(self, data: bytes):
        self.identifier = data[:2].decode("utf-8")
        if not self.is_valid:
            return
        self.id = int.from_bytes(data[2:4], "little")
        self.package = int.from_bytes(data[4:6], "little")
        self.type_ = int.from_bytes(data[6:7], "little")
        _logger.info("Ack: %s", self)

    @property
    def is_valid(self):
        return self.identifier == "AK"

    def __str__(self):
        if self.is_valid:
            return f"File: {self.id}, Type: {self.type_}, Package: {self.package}"
        return "Invalid Request"


class LogMessage:
    def __init__(self, data: bytes):
        self.message = ""
        self.parse(data)

    def parse(self, data: bytes):
        self.identifier = data[:2].decode("utf-8")
        if not self.is_valid:
            return
        self.level = "debug" if self.identifier == "LD" else "error"
        self.message = data[2 : data.index(0)].decode("utf-8")

    @property
    def is_valid(self):
        return self.identifier in ("LE", "LD")

    def __str__(self):
        if self.is_valid:
            return f"{self.level}: {self.message}"
        return "Invalid Request"


def parse_hid_update_message(data: bytes) -> ChunkAck | UpdateError | LogMessage | None:
    if len(data) < 2:
        return None
    val = data[:2].decode("utf-8")
    match val:
        case "AK":
            return ChunkAck(data)
        case "ER":
            return UpdateError(data)
        case "LD", "LE":
            return LogMessage(data)
    return None
