from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from airflow.sdk import BaseSensorOperator
from pydantic import BaseModel, ConfigDict, Field

from ...models.__types import BaseOperatorOrTaskGroup
from ...models.builder import DominoBuilderMixin
from ...models.task import BaseSensorTask

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG
    from airflow.sdk.definitions.taskgroup import TaskGroup

    from ...models.context import BuildContext


class SensorOperatorKwargs(BaseModel, DominoBuilderMixin):
    """Sensor Operator task kwargs."""

    model_config = ConfigDict(extra="forbid")

    airflow_operator: str = Field(
        ...,
        description="The Airflow operator name to be executed in SensorOperator task.",
    )
    op_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="A dictionary of keyword arguments to pass to the Airflow operator.",
    )

    def build(self, build_context: BuildContext) -> dict[str, Any]:
        """Build a dictionary of keyword arguments for the Airflow SensorOperator.

        Args:
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.

        Returns:
            dict[str, Any]: A dictionary of keyword arguments to pass to the
                Operator task that was generated from the model dumping method
                excluded ``airflow_operator``.
        """
        return self.model_dump(exclude={"airflow_operator"})


class SensorTask(BaseSensorTask):
    """Sensor task.

    Examples:

        ```yml
        id: example
        type: sensor
        inputs:
          airflow_operator: operator_name
          op_kwargs:
            param_01: value_01
            param_02: value_02
        poke_interval_sec: 10
        mode: poke
        soft_fail: true
        ```
    """

    type: Literal["sensor"] = "sensor"
    inputs: SensorOperatorKwargs = Field(
        ...,
        description="The input parameters for the Airflow operator.",
    )

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Build an Airflow Operator object.

         Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow Operator object.
        """
        if (
            self.inputs.airflow_operator
            not in build_context["airflow_operators"]
        ):
            raise ValueError(
                f"Operator need to pass to `operators` argument, "
                f"{self.inputs.airflow_operator}, first."
            )
        op = build_context["airflow_operators"][self.inputs.airflow_operator]
        if not isinstance(op, BaseSensorOperator):
            raise ValueError(
                f"Operator {self.inputs.airflow_operator} is not a child of "
                f"Airflow's BaseSensorOperator."
            )
        return build_context["airflow_operators"][self.inputs.airflow_operator](
            dag=dag,
            task_group=task_group,
            **self.inputs.build(build_context=build_context),
            **self.base_op_kwargs(build_context=build_context),
        )
