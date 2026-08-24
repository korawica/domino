from __future__ import annotations

from typing import ClassVar

from .dag import Dag


class DagBlueprint(Dag):
    template_fields: ClassVar[tuple[str, ...]] = ("id",)
