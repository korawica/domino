from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from airflow.providers.standard.operators.python import PythonOperator
from pydantic import BaseModel, ConfigDict, Field

from ...models.builder import DominoBuilderMixin
from ...models.task import BaseOperatorTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.__types import BaseOperatorOrTaskGroup
    from ...models.context import BuildContext


class PythonKwargs(BaseModel, DominoBuilderMixin):
    """Python Operator kwargs."""

    model_config = ConfigDict(extra="forbid")

    python_callable: Any = Field(
        ...,
        description="A Python callable function.",
    )
    op_args: list[Any] | None = Field(
        default=None,
        description="A list of positional arguments to pass to the callable.",
    )
    op_kwargs: dict[str, Any] | None = Field(
        default=None,
        description="A dictionary of keyword arguments to pass to the callable.",
    )
    templates_dict: dict[str, Any] | None = Field(
        default=None,
        description="A dictionary of template fields to render before passing to the callable.",
    )
    templates_exts: list[str] | None = Field(
        default=None,
        description="A list of file extensions to consider as templates.",
    )
    show_return_value_in_logs: bool = Field(
        default=True,
        description="Whether to show the return value of the callable in the logs.",
    )

    def build(self, build_context: BuildContext) -> dict[str, Any]:
        """Build a dictionary of keyword arguments for the PythonOperator.

        Args:
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.

        Returns:
            dict[str, Any]: A dictionary of keyword arguments to pass to the
                Python task that was generated from the model dumping method
                excluded ``python_callable``.
        """
        return self.model_dump(
            exclude={"python_callable"},
            exclude_unset=True,
        )


class PythonTask(BaseOperatorTask):
    """Python task.

    Examples:

        ```yml
        id: example
        type: python
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

    type: Literal["python"] = Field(default="python")
    inputs: PythonKwargs = Field(
        default_factory=PythonKwargs,
        description="A Python callable function and its arguments.",
    )

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Build an Airflow PythonOperator object.

         Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow PythonOperator object.
        """
        if self.inputs.python_callable not in build_context["python_callables"]:
            raise ValueError(
                f"Python task need to pass python function name, "
                f"{self.inputs.python_callable}, first."
            )
        return PythonOperator(
            dag=dag,
            task_group=task_group,
            python_callable=build_context["python_callables"][
                self.inputs.python_callable
            ],
            **self.inputs.build(build_context=build_context),
            **self.base_op_kwargs(build_context=build_context),
        )
