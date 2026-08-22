from typing import Any, Literal

from pydantic import BaseModel, Field


class Variable(BaseModel):
    type: Literal["variable"] = "variable"
    stages: dict[str, dict[str, Any]] = Field(
        ...,
        description="A dictionary of stages and their corresponding variables.",
    )
