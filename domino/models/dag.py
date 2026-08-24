from __future__ import annotations

from typing import Any, ClassVar, Literal

from airflow import DAG
from pydantic import Field

from .label import Label
from .task_group import TaskOrGroup
from .templater import Templater


class Dag(Templater):
    """DAG Model."""

    base_template_fields: ClassVar[tuple[str, ...]] = (
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

    id: str = Field(
        ...,
        description="A unique identifier for the DAG.",
    )
    type: Literal["dag"] = "dag"
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
    start_date: str | None = Field(
        default=None, description="The start date for the DAG."
    )
    end_date: str | None = Field(
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
    ) -> DAG:
        """Build the Airflow DAG from the DAG model."""
        dag = DAG(
            **self.dag_kwargs(
                exclude={
                    "type",
                    "tasks",
                    "labels",
                },
            ),
        )
        return dag
