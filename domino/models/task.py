from abc import ABC
from typing import Literal

from pydantic import Field

from .builder import CoreAirflowTaskOrGroupBuilder


class BaseTask(CoreAirflowTaskOrGroupBuilder, ABC):
    """Base Task Model."""

    id: str = Field(..., description="A unique identifier for the task.")
    type: Literal["basetask"] = "basetask"
