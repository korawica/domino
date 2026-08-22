from typing import Any, Literal

from airflow import DAG
from pydantic import BaseModel, Field

from ..tasks import Task
from .label import Label


class Dag(BaseModel):
    """DAG Model."""

    id: str = Field(..., description="A unique identifier for the DAG.")
    type: Literal["dag"] = "dag"
    desc: str | None = Field(
        default=None, description="A description of the DAG."
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
    start_date: str | None = Field()
    end_date: str | None = Field()
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
    tasks: list[Task] = Field(
        description="A list of tasks associated with the DAG.",
    )

    def dag_kwargs(self) -> dict[str, Any]:
        return self.model_dump(
            exclude_unset=True,
        )

    def build(
        self,
    ) -> DAG:
        """Build the Airflow DAG from the DAG model."""
        dag = DAG(
            dag_id=self.id,
            **self.dag_kwargs(),
        )
        return dag
