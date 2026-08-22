from abc import ABC
from typing import Any

from pydantic import Field

from .builder import BaseAirflowTaskOrGroupBuilder


class BaseOperatorTask(BaseAirflowTaskOrGroupBuilder, ABC):
    """Base Operator Task Model."""

    id: str = Field(..., description="A unique identifier for the task.")
    type: str = Field(..., description="The type of the task.")

    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Input parameters for the task."
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the task."
    )


class BaseSensorTask(BaseOperatorTask, ABC):
    """Base Sensor Task Model."""

    poke_interval_sec: int = Field(
        default=60,
        description="The interval in seconds between each poke.",
    )
    timeout_sec: int = Field(
        default=7 * 24 * 60 * 60,  # 7 days
        description="The maximum time in seconds to wait for the sensor to succeed.",
    )
