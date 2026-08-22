from typing import Annotated, Any, Literal, Union

from pydantic import Field

from ..tasks import Task
from .builder import BaseBuilder


class Group(BaseBuilder):
    """Group Model."""

    id: str = Field(..., description="A unique identifier for the task group.")
    type: Literal["group"] = Field(
        default="group", description="The type of the task group."
    )
    tasks: list[TaskOrGroup] = Field(
        description="A list of Task or Group objects that belong to this group.",
    )

    def build(
        self,
        dag: Any,
        build_context: Any,
        task_group: Any | None = None,
    ) -> Any: ...


TaskOrGroup = Annotated[
    Union[
        Group,
        Task,
    ],
    Field(
        discriminator="type",
        description=(
            "A union of tasks and Group objects, allowing for polymorphic "
            "behavior based on the 'type' field."
        ),
    ),
]
