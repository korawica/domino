from abc import ABC
from typing import Any

from pydantic import Field

from .builder import CoreAirflowTaskOrGroupBuilder


class BaseTask(CoreAirflowTaskOrGroupBuilder, ABC):
    """Base Task Model."""

    id: str = Field(..., description="A unique identifier for the task.")
    type: str = Field(..., description="The type of the task.")

    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Input parameters for the task."
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the task."
    )
