from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from airflow.providers.standard.operators.empty import EmptyOperator
from pydantic import Field

from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.context import BuildContext


class EmptyTask(BaseOperatorTask):
    """Empty Task.

    !!! tip "Airflow Operator: `airflow.providers.standard.operators.empty.EmptyOperator`"

    Examples:

        ```yml
        id: example
        type: empty
        ```
    """

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
