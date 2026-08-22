from typing import TYPE_CHECKING, Any, Literal

from airflow.providers.standard.operators.python import PythonOperator
from pydantic import BaseModel, Field

from domino.models.task import BaseTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.context import BuildContext


class PythonKwargs(BaseModel):
    """Python Task kwargs."""

    python_callable: Any = Field(
        ...,
        description="A Python callable function.",
    )
    op_args: list[Any] = Field(
        default_factory=list,
        description="A list of positional arguments to pass to the callable.",
    )
    op_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="A dictionary of keyword arguments to pass to the callable.",
    )

    def dump_kwargs(self):
        return {
            "python_callable": self.python_callable,
            "op_args": self.op_args,
            "op_kwargs": self.op_kwargs,
        }


class PythonTask(BaseTask):
    """Python Task."""

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
    ) -> Any:
        return PythonOperator(
            task_id=self.id,
            dag=dag,
            task_group=task_group,
            **self.inputs.dump_kwargs(),
        )
