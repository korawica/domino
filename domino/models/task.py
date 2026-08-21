from abc import ABC
from typing import Literal

from pydantic import Field

from .builder import BaseBuilder


class BaseTask(BaseBuilder, ABC):
    id: str = Field(..., description="A unique identifier for the task.")
    type: Literal["basetask"] = "basetask"
