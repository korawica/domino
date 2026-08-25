from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from airflow.providers.standard.operators.bash import BashOperator
from pydantic import BaseModel, ConfigDict, Field

from ...models.builder import DominoBuilderMixin
from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.__types import BaseOperatorOrTaskGroup
    from ...models.context import BuildContext


class BashKwargs(BaseModel, DominoBuilderMixin):
    """Bash Operator kwargs."""

    model_config = ConfigDict(extra="forbid")

    bash_command: str = Field(
        ...,
        description="The command, set of commands or reference to a bash script "
        "to be executed.",
    )

    def build(self, build_context: BuildContext) -> dict[str, Any]:
        """Build a dictionary of keyword arguments for the BashOperator.

        Args:
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
        """
        return self.model_dump()


class BashTask(BaseOperatorTask):
    """Bash Task.

    !!! tip "Airflow Operator: `airflow.providers.standard.operators.bash.BashOperator`"

    Examples:

        ```yml
        id: example
        type: bash
        ```
    """

    type: Literal["bash"] = Field(default="bash")
    inputs: BashKwargs = Field(
        ...,
        description="A dictionary of keyword arguments to pass to the BashOperator.",
    )

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Build an Airflow BashOperator object.

         Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow BashOperator object.
        """
        return BashOperator(
            dag=dag,
            task_group=task_group,
            **self.inputs.build(build_context=build_context),
            **self.base_op_kwargs(build_context=build_context),
        )
