from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from .__types import BaseOperator, BaseOperatorOrTaskGroup

if TYPE_CHECKING:
    from threading import Lock

    from ..renderer import JinjaRenderer
    from .builder import BaseAirflowTaskOrGroupBuilder
    from .label import Label


class TaskContext(TypedDict):
    """Task Context dict typed."""

    task: BaseOperatorOrTaskGroup
    upstreams: list[str]
    teardown: NotRequired[str | None]


class BuildContext(TypedDict):
    """Building Context type dict.

    This building context was created from the DAG Factory object and passed
    to each task build method.
    """

    path: Path
    label: Label
    jinja_renderer: JinjaRenderer

    # task Factory context
    tasks: dict[str, TaskContext]
    tasks_lock: NotRequired[Lock]
    dataset_hook: NotRequired[Callable[..., Any]]

    # assets context
    task_objects: dict[str, type[BaseAirflowTaskOrGroupBuilder]]
    python_callables: dict[str, Callable[..., Any]]
    airflow_operators: dict[str, type[BaseOperator]]
