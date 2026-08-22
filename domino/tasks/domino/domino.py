from typing import Literal

from airflow import DAG
from airflow.sdk import TaskGroup
from pydantic import BaseModel, Field

from ...models.__types import BaseOperatorOrTaskGroup
from ...models.context import BuildContext
from ...models.task import BaseTask


class DominoInput(BaseModel):
    task_object: str = Field(
        ..., description="The task object to be executed in Domino."
    )


class DominoTask(BaseTask):
    type: Literal["domino"] = "domino"

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup: ...
