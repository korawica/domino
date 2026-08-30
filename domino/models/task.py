from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self

from airflow.sdk import TriggerRule
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationInfo
from pydantic.functional_validators import model_validator

from .builder import BaseAirflowTaskOrGroupBuilder

if TYPE_CHECKING:
    from .context import BuildContext


class BaseOperatorTask(BaseAirflowTaskOrGroupBuilder, ABC):
    """Base Operator Task Model.

    !!! tip "Reference Airflow Operator: `airflow.sdk.bases.operator.BaseOperator`"
    """

    model_config = ConfigDict(
        # Use enum values for the ``trigger_rule`` field instead of the enum names.
        use_enum_values=True,
    )

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
    upstreams: list[str] = Field(
        default_factory=list,
        description="A list of upstream task IDs for the task.",
    )
    teardown: str | None = Field(
        default=None,
        description=(
            "A setup task ID that will need to run before this task. "
            "[Read more about setup and teardown in the Airflow](https://airflow.apache.org/docs/apache-airflow/stable/howto/setup-and-teardown.html)."
        ),
    )
    trigger_rule: TriggerRule = Field(
        default=TriggerRule.ALL_SUCCESS,
        description="The trigger rule for the task.",
        # Allow to validate itself because the default passing with Enum value.
        validate_default=True,
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

    # Custom callback fields that set on the task layer.
    on_failure_callback: list[str] | None = Field(
        default=None,
        description=(
            "A name of function or list of function names that will be called "
            "when a task instance of this task fails. a context dictionary is "
            "passed as a single parameter to this function. Context contains "
            "references to related objects to the task instance and is "
            "documented under the macros section of the API."
        ),
    )
    on_execute_callback: list[str] | None = Field(
        default=None,
        description=(
            "much like the ``on_failure_callback`` except that it is executed "
            "right before the task is executed."
        ),
    )
    on_retry_callback: list[str] | None = Field(
        default=None,
        description=(
            "much like the ``on_failure_callback`` except that it is executed "
            "when retries occur."
        ),
    )
    on_success_callback: list[str] | None = Field(
        default=None,
        description=(
            "much like the ``on_failure_callback`` except that it is executed "
            "when the task succeeds."
        ),
    )
    on_skipped_callback: list[str] | None = Field(
        default=None,
        description=(
            "much like the ``on_failure_callback`` except that it is executed "
            "when skipped occur; this callback will be called only if AirflowSkipException "
            "get raised. Explicitly it is NOT called if a task is not started "
            "to be executed because of a preceding branching decision in the "
            "DAG or a trigger rule which causes execution to skip so that the "
            "task execution is never scheduled."
        ),
    )

    # Private field for keeping all mapping of task callbacks and its
    #   callback function that will use on the building step.
    _callbacks: dict[str, list[Any]] = PrivateAttr(
        default_factory=dict,
        init=False,
    )

    @model_validator(mode="after")
    def inject_callbacks(self, info: ValidationInfo) -> Self:
        """Inject the callback fields with the task callbacks that already pass in
        the context from DAG Factory.

        This method will collect the callback value from the context and map it
        to the callback fields if the name of the callback exist in the field
        value.

        Args:
            info (ValidationInfo): A validation info that pass after validating
                the model.

        Returns:
            Self: A validated model with the task callbacks that already mapping
                from the callback fields.
        """
        callback_fields: dict[str, list[str]] = {  # type: ignore
            "on_failure_callback": self.on_failure_callback,
            "on_success_callback": self.on_success_callback,
            "on_execute_callback": self.on_execute_callback,
            "on_retry_callback": self.on_retry_callback,
            "on_skipped_callback": self.on_skipped_callback,
        }

        # NOTE: Deduplicate callbacks name that want to inject.
        callback_dedup: dict[str, set[str]] = {
            field: set(names)
            for field, names in callback_fields.items()
            if (names is not None) and names
        }

        if info.context and "task_callbacks" in info.context:
            callbacks: dict[str, Any] = info.context["task_callbacks"]
            # Build reverse map: name → fields, so each callback lookup is O(1)
            # instead of scanning all fields per callback.
            name_to_fields: dict[str, list[str]] = {}
            for field, names in callback_dedup.items():
                for name in names:
                    name_to_fields.setdefault(name, []).append(field)

            collected: dict[str, list[Any]] = {k: [] for k in callback_dedup}
            for k, v in callbacks.items():
                for field in name_to_fields.get(k, ()):
                    collected[field].append(v)

            self._callbacks.update({f: v for f, v in collected.items() if v})

        return self

    def base_op_kwargs(self, build_context: BuildContext) -> dict[str, Any]:
        """Returns the keyword arguments for the Airflow BaseOperator.

        Args:
            build_context (BuildContext): A build context that was passed from
                the factory.

        Returns:
            dict[str, Any]: A mapping of Airflow's BaseOperator keyword
                arguments.
        """
        set_kws = self.model_dump(
            by_alias=True,
            exclude_unset=True,
            exclude={
                "type",
                "desc",
                "upstreams",
                "teardown",
            },
        )

        set_kws["task_id"] = set_kws.pop("id")
        _ = build_context
        return set_kws


class BaseSensorMixin(BaseModel):
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

    def sensor_kwargs(self, build_context: BuildContext) -> dict[str, Any]:
        """Returns the keyword arguments for the Airflow BaseSensorOperator."""
        _ = build_context
        kws = self.model_dump(
            include={
                "poke_interval_sec",
                "timeout_sec",
                "soft_fail",
                "mode",
                "exponential_backoff",
                "max_wait_sec",
                "silent_fail",
                "never_fail",
            },
            exclude_unset=True,
        )
        return kws
