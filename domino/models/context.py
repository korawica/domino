from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from .__types import BaseOperator, BaseOperatorOrTaskGroup

if TYPE_CHECKING:
    from threading import Lock

    from .label import Label


class TaskContext(TypedDict):
    """Task Context dict typed."""

    task: BaseOperatorOrTaskGroup
    upstream: list[str]
    teardown: NotRequired[str | None]


class BuildContext(TypedDict):
    """Building Context type dict."""

    label: Label
    tasks: dict[str, TaskContext]
    tasks_lock: NotRequired[Lock]

    task_objects: dict[str, Any]
    python_callables: dict[str, Any]
    airflow_operators: dict[str, BaseOperator]
