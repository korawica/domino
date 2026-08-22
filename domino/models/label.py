from typing import Literal

from pydantic import BaseModel, Field

PriorityType = Literal["p1", "p2", "p3", "p4", "p5"]


class Label(BaseModel):
    """Label Model."""

    team: str | None = Field(
        default=None,
        description="The team responsible for the task.",
    )
    system: str | None = Field(
        default=None,
        description="The system responsible for the task.",
    )
    priority: PriorityType | None = Field(
        default=None,
        description="The priority of the task.",
    )

    def make_tags(self) -> list[str]:
        """Make tags from labels."""
        return [
            f"{key}:{value}"
            for key, value in self.model_dump(exclude_none=True).items()
        ]
