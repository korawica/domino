from typing import Literal

from airflow import DAG
from airflow.sdk import TaskGroup
from airflow.sdk.bases.operator import BaseOperator
from pydantic import BaseModel, Field

from domino.models.__types import BaseOperatorOrTaskGroup
from domino.models.context import BuildContext

from ...models.task import BaseOperatorTask


class ErrorOperator(BaseOperator):
    def __init__(self, *args, message: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message


class ErrorInput(BaseModel):
    message: str | None = Field(default=None)


class ErrorTask(BaseOperatorTask):
    type: Literal["error"] = "error"
    input: ErrorInput = Field(
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
            message=self.input.message,
        )
