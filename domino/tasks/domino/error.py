from __future__ import annotations

from typing import Any, Literal

from airflow import DAG
from airflow.sdk import Context, TaskGroup
from airflow.sdk.bases.operator import BaseOperator
from airflow.sdk.exceptions import AirflowException, AirflowSkipException
from pydantic import BaseModel, Field

from domino.models.__types import BaseOperatorOrTaskGroup
from domino.models.context import BuildContext

from ...models.task import BaseOperatorTask


class ErrorOperator(BaseOperator):
    """Error Operator."""

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

    message: str | None = Field(
        default=None, description="An error message that want to show."
    )
    soft_fail: bool = Field(
        default=False,
        description="Whether or not to show a soft failure message.",
    )


class ErrorTask(BaseOperatorTask):
    """Error task."""

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
        return ErrorOperator(
            task_id=self.id,
            dag=dag,
            task_group=task_group,
            message=self.inputs.message,
            soft_fail=self.inputs.soft_fail,
        )
