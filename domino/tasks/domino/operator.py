from typing import TYPE_CHECKING, Literal

from airflow import DAG
from airflow.sdk import TaskGroup
from pydantic import Field

from ...models.__types import BaseOperatorOrTaskGroup
from ...models.context import BuildContext
from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from airflow.sdk.bases.operator import BaseOperator


class OperatorTask(BaseOperatorTask):
    """Operator Task.

    Examples:

        ```yml
        id: example
        type: operator
        airflow_operator: operator_name
        inputs:
          operator_param_01: value_01
          operator_param_02: value_02
        ```
    """

    type: Literal["operator"] = "operator"
    airflow_operator: str = Field(
        ...,
        description="The Airflow operator name to be executed in Operator task.",
    )

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        airflow_operators: dict[str, type[BaseOperator]] = build_context[
            "airflow_operators"
        ]
        if self.airflow_operator not in airflow_operators:
            raise ValueError(
                f"Operator need to pass to `operators` argument, "
                f"{self.airflow_operator}, first."
            )
        op: type[BaseOperator] = airflow_operators[self.airflow_operator]
        return op(
            dag=dag,
            task_group=task_group,
            **self.inputs,
            **self.task_kwargs(build_context=build_context),
        )
