import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .loader import SingleDagLoader
from .utils import get_dags_path

if TYPE_CHECKING:
    from airflow import DAG
    from airflow.sdk.bases.operator import BaseOperator

    from .models.dag import Dag
    from .models.task import BaseTask

logger = logging.getLogger("domino")


class SingleDagGenerator:
    """Single DAG Generator object."""

    __slots__ = (
        "path",
        "is_under_dags_dir",
        "loader",
        "conf",
        "on_success_callback",
        "on_failure_callback",
        "python_callables",
        "task_objects",
        "airflow_operators",
    )

    def validate_path(self, path: Path | str) -> Path:
        """Validate the path parameter that passing for generating Airflow DAG."""
        path = path if isinstance(path, Path) else Path(path)

        # Path of DAG template should be directory
        if not path.is_dir():
            path = path.parent

        if (
            (dags_path := get_dags_path())
            and path != dags_path
            and dags_path not in path
        ):
            self.is_under_dags_dir = True
            logger.warning(
                f"⚠️ The template path: {path} is not under the Airflow "
                f"``dags_folder``, {dags_path}."
            )
        return path

    def __init__(
        self,
        /,
        path: Path | str,
        *,
        # Backend callbacks
        on_success_callback: list[Any] | None = None,
        on_failure_callback: list[Any] | None = None,
        # Backend assets
        python_callables: dict[str, Callable[..., None]] | None = None,
        task_objects: dict[str, BaseTask] | None = None,
        airflow_operators: dict[str, BaseOperator] | None = None,
    ) -> None:
        """Initialize the DAG Generator.

        Args:
            path (Path | str): Path to the DAG template folder.
        """
        self.is_under_dags_dir = True
        self.path = self.validate_path(path=path)

        self.on_success_callback = on_success_callback or []
        self.on_failure_callback = on_failure_callback or []

        # Backend assets for specific tasks.
        self.python_callables = python_callables or {}
        self.task_objects = task_objects or {}
        self.airflow_operators = airflow_operators or {}

        self.loader = SingleDagLoader(self.path)
        self.conf: Dag | None = None

    @property
    def dag(self) -> Dag:
        """Get the DAG model from the DAG template."""
        dag: Dag | None = self.conf
        if dag is None:
            dag: Dag = self.loader.read_dag()
            self.conf = dag
            return dag
        return dag

    def build(self) -> DAG:
        model: Dag = self.dag
        dag = model.build()
        return dag

    def build_airflow_dag_to_globals(self, gb: dict[str, Any]) -> None:
        """Build Airflow DAG to the globals.

        Args:
            gb (dict[str, Any]): The Global variables.
        """
        dag: DAG = self.build()
        gb[dag.dag_id] = dag

    def parse(self) -> dict[str, Any]:
        """Pre parsing the DAG template.

        Returns:
            dict[str, Any]: A DAG template data after passing all variables.
        """
        model: Dag = self.dag
        return model.model_dump()
