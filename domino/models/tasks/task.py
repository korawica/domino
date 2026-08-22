from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from domino.models.tasks.builder import BaseTaskOrGroup


class Task(BaseTaskOrGroup):
    id: str = Field(..., description="A unique identifier for the task.")
    type: Literal["task"] = "task"

    def build(
        self,
        dag: Any,
        build_context: Any,
        task_group: Any | None = None,
    ) -> Any: ...
