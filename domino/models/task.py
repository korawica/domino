from abc import ABC

from pydantic import Field

from .builder import CoreAirflowTaskOrGroupBuilder


class BaseTask(CoreAirflowTaskOrGroupBuilder, ABC):
    """Base Task Model."""

    id: str = Field(..., description="A unique identifier for the task.")
    type: str = Field(..., description="The type of the task.")
