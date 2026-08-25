from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import pendulum
from airflow import DAG
from pendulum import DateTime, parse
from pydantic import ConfigDict, Field
from pydantic.functional_validators import field_validator

from .label import Label
from .task_group import TaskOrGroup
from .templater import Templater

if TYPE_CHECKING:
    from .context import BuildContext


class Dag(Templater):
    """DAG Model."""

    model_config = ConfigDict(
        # Allow to accept pendulum.DateTime type
        arbitrary_types_allowed=True,
    )

    base_template_fields: ClassVar[tuple[str, ...]] = (
        "docs",
        "owners",
        "tags",
        "labels",
        "schedule",
        "start_date",
        "end_date",
        "catchup",
        "max_active_tasks",
        "max_active_runs",
        "max_consecutive_failed_dag_runs",
        "dagrun_timeout_sec",
    )
    base_template_fields_ext: ClassVar[dict[str, tuple[str, ...]]] = {
        "docs": (".md",),
    }

    id: str = Field(
        ...,
        description="A unique identifier for the DAG.",
    )
    type: Literal["dag"] = "dag"
    docs: str | None = Field(
        default=None,
        description=(
            "A documentation for the DAG that allows to render in Airflow UI "
            "with Markdown format only."
        ),
    )
    desc: str | None = Field(
        default=None,
        description="A description of the DAG.",
    )
    owners: list[str] = Field(
        default_factory=list, description="A list of owners of the DAG."
    )
    tags: list[str] = Field(
        default_factory=list,
        description="A list of tags associated with the DAG.",
    )
    labels: Label = Field(
        default_factory=Label,
        description="A set of labels associated with the DAG.",
    )

    schedule: str | None = Field(
        default=None,
        description="The schedule interval for the DAG, in cron format or a preset.",
    )
    start_date: DateTime | None = Field(
        default=None, description="The start date for the DAG."
    )
    end_date: DateTime | None = Field(
        default=None, description="The end date for the DAG."
    )
    catchup: bool | None = Field(
        default=None,
        description="Whether the DAG should catch up on missed runs.",
    )

    max_active_tasks: int | None = Field(
        default=None,
        description="The maximum number of active tasks for the DAG.",
    )
    max_active_runs: int | None = Field(
        default=None,
        description="The maximum number of active runs for the DAG.",
    )
    max_consecutive_failed_dag_runs: int | None = Field(
        default=None,
        description="The maximum number of consecutive failed DAG runs.",
    )
    dagrun_timeout_sec: int | None = Field(
        default=None,
        description="The timeout for a DAG run, in seconds.",
    )

    # Task models
    tasks: list[TaskOrGroup] = Field(
        description="A list of tasks associated with the DAG.",
    )

    @field_validator(
        "start_date",
        "end_date",
        mode="before",
    )
    @classmethod
    def validate_datetime(cls, data: Any) -> DateTime | None:
        if isinstance(data, str):
            if data.lower() in ("null", "none"):
                return None

            return cast(DateTime, parse(data, strict=True, exact=False))
        elif data and isinstance(data, datetime):
            if data.tzinfo is None:
                return pendulum.instance(data)
            return pendulum.instance(data)
        return data

    def dag_kwargs(self, exclude: set[str] | None = None) -> dict[str, Any]:
        """Return the DAG keyword arguments from the DAG model that will use
        to passing to Airflow DAG object.
        """
        kws = self.model_dump(
            exclude=exclude,
            exclude_unset=True,
        )
        kws["dag_id"] = kws.pop("id")
        kws["description"] = kws.pop("desc", None)
        return kws

    def build(
        self,
        build_context: BuildContext,
    ) -> DAG:
        """Build the Airflow DAG from the DAG model."""
        label: Label = build_context["label"]
        dag = DAG(
            tags=set(self.tags) | label.make_tags(),
            **self.dag_kwargs(
                exclude={
                    "type",
                    "tasks",
                    "labels",
                    "tags",
                },
            ),
        )
        return dag
