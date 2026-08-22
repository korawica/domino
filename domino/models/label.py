from typing import Literal

from pydantic import BaseModel, Field

PriorityType = Literal["p1", "p2", "p3"]


class Label(BaseModel):
    team: str = Field(
        default="notset",
        description="The team responsible for the task.",
    )
    system: str = Field(
        default="notset",
        description="The system responsible for the task.",
    )
    priority: PriorityType = Field(
        default="p3",
        description="The priority of the task.",
    )
