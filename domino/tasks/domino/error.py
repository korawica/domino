from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from airflow.sdk.bases.operator import BaseOperator
from airflow.sdk.exceptions import AirflowException, AirflowSkipException
from pydantic import BaseModel, ConfigDict, Field

from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from airflow.sdk import Context
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.__types import BaseOperatorOrTaskGroup
    from ...models.context import BuildContext


class ErrorOperator(BaseOperator):
    """Error operator.

    This class inherits from the Airflow BaseOperator and is used to raise an
    error during the execution of a task. It can be configured to either raise
    a hard failure (AirflowException) or a soft failure (AirflowSkipException)
    based on the `soft_fail` parameter.
    """

    def __init__(
        self,
        *,
        message: str | None = None,
        soft_fail: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.message = message
        self.soft_fail = soft_fail

    def execute(self, context: Context) -> Any:
        if self.soft_fail:
            raise AirflowSkipException(self.message)
        raise AirflowException(self.message)


class ErrorInput(BaseModel):
    """Error Input model."""

    model_config = ConfigDict(extra="forbid")

    message: str | None = Field(
        default=None, description="An error message that want to show."
    )
    soft_fail: bool = Field(
        default=False,
        description="Whether or not to show a soft failure message.",
    )


class ErrorTask(BaseOperatorTask):
    """Error task.

    !!! tip "Domino Operator: `domino.tasks.domino.error.ErrorOperator`"

    Examples:

        ```yml
        id: example
        type: error
        inputs:
          message: "This is an error message."
          soft_fail: False
        ```
    """

    type: Literal["error"] = "error"
    inputs: ErrorInput = Field(
        default_factory=ErrorInput,
        description="Input parameters for the raise task.",
    )

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Build an Airflow ErrorOperator object.

         Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow ErrorOperator object.
        """
        return ErrorOperator(
            dag=dag,
            task_group=task_group,
            message=self.inputs.message,
            soft_fail=self.inputs.soft_fail,
            **self.base_op_kwargs(build_context=build_context),
        )
