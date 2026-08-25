from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from airflow.providers.standard.operators.trigger_dagrun import (
    TriggerDagRunOperator,
)
from pydantic import Field

from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.__types import BaseOperatorOrTaskGroup
    from ...models.context import BuildContext


class TriggerDagRunTask(BaseOperatorTask):
    """TriggerDagRun Task.

    !!! tip "Airflow Operator: `airflow.providers.standard.operators.trigger_dagrun.TriggerDagRunOperator`"

    Examples:

        ```yml
        id: example
        type: trigger_dagrun
        ```
    """

    type: Literal["trigger_dagrun"] = Field(default="trigger_dagrun")

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Build an Airflow TriggerDagRunOperator object.

         Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow TriggerDagRunOperator object.
        """
        return TriggerDagRunOperator(
            dag=dag,
            task_group=task_group,
            **self.base_op_kwargs(build_context=build_context),
        )
