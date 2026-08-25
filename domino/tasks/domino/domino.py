from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...models.__types import BaseOperatorOrTaskGroup
from ...models.builder import DominoBuilderMixin
from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.builder import BaseAirflowTaskOrGroupBuilder
    from ...models.context import BuildContext


class DominoTaskKwargs(BaseModel, DominoBuilderMixin):
    """Domino task kwargs."""

    model_config = ConfigDict(extra="forbid")

    task_object: str = Field(
        ...,
        description="The task object to be executed in Domino.",
    )
    task_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="A dictionary of keyword arguments to pass to the Domino task.",
    )

    def build(self, build_context: BuildContext) -> dict[str, Any]:
        """Build a dictionary of keyword arguments for the Domino task.

        Args:
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.

        Returns:
            dict[str, Any]: A dictionary of keyword arguments to pass to the
                Domino task that was generated from the model dumping method
                excluded ``task_object``.
        """
        return self.model_dump(exclude={"task_object"})


class DominoTask(BaseOperatorTask):
    """Domino task.

    Examples:

        ```yml
        id: example
        type: domino
        inputs:
          task_object: my_domino_task
          task_kwargs:
            key_01: value_01
            key_02: value_02
        ```
    """

    type: Literal["domino"] = "domino"
    inputs: DominoTaskKwargs = Field(
        ...,
        description="A dictionary of keyword arguments to pass to the Domino task.",
    )

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Build an Airflow Operator or TaskGroup object from the building result
        of its Domino task.

        Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow Operator or TaskGroup object
                from the building result of its Domino task.
        """
        if self.inputs.task_object not in build_context["task_objects"]:
            raise ValueError(
                f"Task object need to pass to `task_objects` argument for "
                f"{self.inputs.task_object!r} first."
            )

        if (
            "jinja_renderer" not in build_context
            or build_context["jinja_renderer"] is None
        ):
            raise ValueError(
                f"Task builder need to pass to `jinja_renderer` argument "
                f"for {self.inputs.task_object!r}."
            )

        model: BaseAirflowTaskOrGroupBuilder = build_context["task_objects"][
            self.inputs.task_object
        ].model_validate(
            obj={"id": self.id} | self.inputs.model_dump(),
            context={"jinja_renderer": build_context["jinja_renderer"]},
        )
        return model.build(
            dag=dag,
            task_group=task_group,
            build_context=build_context,
        )
