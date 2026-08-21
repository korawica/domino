from typing import TYPE_CHECKING, NotRequired, TypedDict

from .__types import OperatorOrTaskGroup

if TYPE_CHECKING:
    from threading import Lock

    from .builder import TaskContext
    from .label import Label


class TaskContext(TypedDict):
    """Task Context dict typed."""

    task: OperatorOrTaskGroup
    upstream: list[str]
    teardown: NotRequired[str | None]


class BuildContext(TypedDict):
    """Building Context type dict."""

    label: Label
    tasks: dict[str, TaskContext]
    tasks_lock: NotRequired[Lock]
