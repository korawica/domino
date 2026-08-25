from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from airflow.providers.standard.operators.python import (
    BranchPythonOperator,
)
from pydantic import Field

from .python import PythonTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.__types import BaseOperatorOrTaskGroup
    from ...models.context import BuildContext


class BranchPythonTask(PythonTask):
    """Branch Python Task.

    !!! tip "Airflow Operator: `airflow.providers.standard.operators.python.BranchPythonOperator`"

    Examples:

        ```yml
        id: example
        type: branch_python
        inputs:
          python_callable: my_function
          op_args:
            - arg1
            - arg2
          op_kwargs:
            kwarg1: value1
            kwarg2: value2
        ```
    """

    type: Literal["branch_python"] = Field(default="branch_python")

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Build an Airflow BranchPythonOperator object.

         Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow BranchPythonOperator object.
        """
        if self.inputs.python_callable not in build_context["python_callables"]:
            raise ValueError(
                f"Branch Python task need to pass python function name, "
                f"{self.inputs.python_callable}, first."
            )
        return BranchPythonOperator(
            dag=dag,
            task_group=task_group,
            python_callable=build_context["python_callables"][
                self.inputs.python_callable
            ],
            **self.inputs.build(build_context=build_context),
            **self.base_op_kwargs(build_context=build_context),
        )
