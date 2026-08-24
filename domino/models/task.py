from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from airflow.sdk import TriggerRule
from pydantic import Field

from .builder import BaseAirflowTaskOrGroupBuilder

if TYPE_CHECKING:
    from .context import BuildContext


class BaseOperatorTask(BaseAirflowTaskOrGroupBuilder, ABC):
    """Base Operator Task Model.

    !!! tip "Reference Airflow Operator: `airflow.sdk.bases.operator.BaseOperator`"
    """

    base_template_fields: ClassVar[tuple[str, ...]] = (
        "desc",
        "params",
        "inlets",
        "outlets",
    )

    id: str = Field(..., description="A unique identifier for the task.")
    type: str = Field(..., description="The type of the task.")
    desc: str | None = Field(
        default=None, description="A description of the task."
    )
    upstream: list[str] = Field(
        default_factory=list,
        description="A list of upstream task IDs for the task.",
    )
    trigger_rule: TriggerRule = Field(
        default=TriggerRule.ALL_SUCCESS,
        description="The trigger rule for the task.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the task.",
    )

    inlets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="A list of inlets for the task.",
    )
    outlets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="A list of outlets for the task.",
    )

    def base_op_kwargs(self, build_context: BuildContext) -> dict[str, Any]:
        """Returns the keyword arguments for the Airflow BaseOperator.

        Args:
            build_context (BuildContext): A build context that was passed from
                the factory.
        """
        set_kws = self.model_dump(
            by_alias=True,
            exclude_unset=True,
            exclude={
                "type",
                "desc",
            },
        )

        set_kws["task_id"] = set_kws.pop("id")
        _ = build_context
        return set_kws


class BaseSensorTask(BaseOperatorTask, ABC):
    """Base Sensor Task Model.

    !!! tip "Reference Airflow Sensor: `airflow.sdk.bases.sensor.BaseSensorOperator`"
    """

    poke_interval_sec: float = Field(
        default=60,
        description="The interval in seconds between each poke.",
    )
    timeout_sec: float | None = Field(
        # default=7 * 24 * 60 * 60,  # 7 days
        default=None,
        description="The maximum time in seconds to wait for the sensor to succeed.",
    )
    soft_fail: bool = Field(
        default=False,
        description="Whether to mark the task as skipped on failure.",
    )
    mode: Literal["poke", "reschedule"] = Field(
        default="poke",
        description="The mode of the sensor.",
    )
    exponential_backoff: bool = Field(
        default=False,
        description="Whether to use exponential backoff for the poke interval.",
    )
    max_wait_sec: float | None = Field(
        default=None,
        description="The maximum wait interval between pokes",
    )
    silent_fail: bool = Field(
        default=False,
        description="Whether to suppress failure messages.",
    )
    never_fail: bool = Field(
        default=False,
        description=(
            "If true, and poke method raises an exception, sensor will be "
            "skipped. Mutually exclusive with ``soft_fail``"
        ),
    )

    def sensor_kwargs(self): ...
