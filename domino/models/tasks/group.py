from typing import Annotated, Any, Literal, Union

from pydantic import Field

from domino.models.tasks.base_builder import BaseTaskOrGroup
from domino.models.tasks.base_task import BaseTask


class Group(BaseTaskOrGroup):
    id: str = Field(..., description="A unique identifier for the task group.")
    type: Literal["group"] = "group"
    tasks: list[TaskOrGroup] = Field(
        ...,
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
        BaseTask,
    ],
    Field(
        discriminator="type",
        description=(
            "A union of BaseTask and Group objects, allowing for polymorphic "
            "behavior based on the 'type' field."
        ),
    ),
]
