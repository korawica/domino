from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from airflow import DAG
from airflow.sdk import TaskGroup
from pydantic import Field

from ...models.__types import BaseOperatorOrTaskGroup
from ...models.context import BuildContext
from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from ...models.builder import BaseAirflowTaskOrGroupBuilder


class DominoTask(BaseOperatorTask):
    """Domino task.

    Examples:

        ```yml
        id: example
        type: domino
        task_object: my_domino_task
        inputs:
          task_kwargs_01: value_01
          task_kwargs_02: value_02
        ```
    """

    type: Literal["domino"] = "domino"
    task_object: str = Field(
        ..., description="The task object to be executed in Domino."
    )

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        task_objects: dict[str, type[BaseAirflowTaskOrGroupBuilder]] = (
            build_context["task_objects"]
        )
        if self.task_object not in task_objects:
            raise ValueError(
                f"Task object need to pass to `task_objects` argument for "
                f"{self.task_object!r} first."
            )
        task: type[BaseAirflowTaskOrGroupBuilder] = task_objects[
            self.task_object
        ]

        if (
            "jinja_renderer" not in build_context
            or build_context["jinja_renderer"] is None
        ):
            raise ValueError(
                f"Task builder need to pass to `jinja_renderer` argument "
                f"for {self.task_object!r}."
            )

        model: BaseAirflowTaskOrGroupBuilder = task.model_validate(
            obj={"id": self.id} | self.inputs,
            context={"jinja_renderer": build_context["jinja_renderer"]},
        )
        return model.build(
            dag=dag,
            task_group=task_group,
            build_context=build_context,
        )
