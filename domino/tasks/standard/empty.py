from typing import TYPE_CHECKING, Any, Literal

from airflow.providers.standard.operators.empty import EmptyOperator
from pydantic import Field

from domino.models.task import BaseTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.context import BuildContext


class EmptyTask(BaseTask):
    """Empty Task."""

    type: Literal["empty"] = Field(default="empty")

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> Any:
        return EmptyOperator(
            task_id=self.id,
            dag=dag,
            task_group=task_group,
        )
