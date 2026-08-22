from abc import ABC
from typing import Any, ClassVar

from pydantic import Field

from .builder import BaseAirflowTaskOrGroupBuilder


class BaseOperatorTask(BaseAirflowTaskOrGroupBuilder, ABC):
    """Base Operator Task Model."""

    base_template_fields: ClassVar[tuple[str, ...]] = (
        "inputs",
        "params",
        "inlets",
        "outlets",
    )

    id: str = Field(..., description="A unique identifier for the task.")
    type: str = Field(..., description="The type of the task.")
    desc: str | None = Field(
        default=None, description="A description of the task."
    )
    upstream: list[str] = Field(
        default_factory=list,
        description="A list of upstream task IDs for the task.",
    )
    trigger_rule: str = Field(
        default="all_success",
        description="The trigger rule for the task.",
    )

    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Input parameters for the task."
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the task."
    )

    inlets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="A list of inlets for the task.",
    )
    outlets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="A list of outlets for the task.",
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
