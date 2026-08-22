from abc import ABC
from typing import Literal

from pydantic import Field

from .task import BaseTask


class BaseSensor(BaseTask, ABC):
    """Base Sensor Model."""

    type: Literal["sensor"] = "sensor"
    poke_interval_sec: int = Field(
        default=60,
        description="The interval in seconds between each poke.",
    )
