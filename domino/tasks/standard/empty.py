from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from airflow.providers.standard.operators.empty import EmptyOperator
from pydantic import Field

from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.__types import BaseOperatorOrTaskGroup
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
    ) -> BaseOperatorOrTaskGroup:
        """Build an Airflow EmptyOperator object.

         Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow EmptyOperator object.
        """
        return EmptyOperator(
            dag=dag,
            task_group=task_group,
            **self.base_op_kwargs(build_context=build_context),
        )
