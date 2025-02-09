# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
from pydantic import BaseModel
from pydantic import Field


class ButtonRequest(BaseModel):
    button: int = Field(..., description="The button to trigger")


class LedRequest(BaseModel):
    button: int = Field(..., description="The button to set the color of")
    color: str = Field(..., description="The color to set the LED to")
