from typing import Literal

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

    tasks: list[Task] = Field(
        description="A list of tasks associated with the DAG.",
    )

    def build(
        self,
    ) -> DAG:
        dag = DAG(
            dag_id=self.id,
        )
        return dag
