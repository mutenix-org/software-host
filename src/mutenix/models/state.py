from enum import Enum

import pydantic
from mutenix.models.config import Config
from mutenix.models.teams_messages import ServerMessage


class ConnectionState(str, Enum):
    """The status of the connection."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

    def __bool__(self):
        return self == ConnectionState.CONNECTED


class HardwareState(pydantic.BaseModel):
    """The hardware information."""

    variant: str = pydantic.Field(description="The hardware variant.", default="NONE")
    version: str = pydantic.Field(description="The hardware version.", default="0.0.0")
    connection_status: ConnectionState = pydantic.Field(
        description="The hardware connection status.",
        default=ConnectionState.DISCONNECTED,
    )
    last_successful_communication: float = pydantic.Field(
        description="The last successful communication time.",
        default=0,
    )
    manufacturer: str = pydantic.Field(
        description="The manufacturer of the hardware.",
        default="Mutenix",
    )
    product: str = pydantic.Field(description="The product name.", default="Macropad")
    serial_number: str = pydantic.Field(
        description="The serial number of the hardware.",
        default="",
    )
    last_button_pressed: int = pydantic.Field(
        description="The last button pressed.",
        default=-1,
    )


class TeamsState(pydantic.BaseModel):
    """The Teams information."""

    connection_status: ConnectionState = pydantic.Field(
        description="The Teams connection status.",
        default=ConnectionState.DISCONNECTED,
    )
    state: ServerMessage = pydantic.Field(
        description="The state teams has reported.",
        default_factory=ServerMessage,
    )
    last_received_timestamp: float = pydantic.Field(
        description="The last time a message was received.",
        default=0,
    )


class VirtualMacropadState(pydantic.BaseModel):
    """The state of the VirtualMacropad."""

    connection_status: ConnectionState = pydantic.Field(
        description="The connection status.",
        default=ConnectionState.DISCONNECTED,
    )


class State(pydantic.BaseModel):
    """The state of the system."""

    hardware: HardwareState = pydantic.Field(
        description="The hardware information.",
        default_factory=HardwareState,
    )
    teams: TeamsState = pydantic.Field(
        description="The Teams information.",
        default_factory=TeamsState,
    )
    config: Config = pydantic.Field(
        description="The loaded configuration.",
        default_factory=Config,
    )

    shutdown_requested: bool = pydantic.Field(
        description="Whether a shutdown has been requested.",
        default=False,
    )
