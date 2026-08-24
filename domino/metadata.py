from __future__ import annotations

from pathlib import Path

from .factory import DagFactory


class BlueprintFactory(DagFactory):
    """Blueprint Factory."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class DagMetadata:
    """DAG Metadata."""

    def __init__(
        self,
        path: Path | str,
        blueprint_path: Path | str | None = None,
    ):
        self.path = path
        self.blueprint_path = blueprint_path
