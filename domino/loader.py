from pathlib import Path

from .models.dag import Dag


class SingleDagLoader:
    __slots__ = ("path",)

    def __init__(self, path: Path):
        self.path = path

    def read_dag(self) -> Dag: ...
