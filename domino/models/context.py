from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from threading import Lock

    from domino.models.builder import TaskContext

    from .label import Label


class BuildContext(TypedDict):
    """Building Context type dict."""

    label: Label
    tasks: dict[str, TaskContext]
    tasks_lock: NotRequired[Lock]
