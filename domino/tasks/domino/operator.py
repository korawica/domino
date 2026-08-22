from typing import Literal

from airflow import DAG
from airflow.sdk import TaskGroup
from pydantic import BaseModel, Field

from ...models.__types import BaseOperatorOrTaskGroup
from ...models.context import BuildContext
from ...models.task import BaseTask


class OperatorInput(BaseModel):
    airflow_operator: str = Field(
        ...,
        description="The Airflow operator name to be executed in Operator task.",
    )


class OperatorTask(BaseTask):
    type: Literal["operator"] = "operator"

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup: ...
