from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from .const import VAR_DOMINO_UNITTEST_MODE
from .loader import DagLoader
from .models.dag import Dag
from .renderer import JinjaRender
from .utils import get_bool_env, get_dags_path

if TYPE_CHECKING:
    from airflow import DAG
    from airflow.sdk.bases.operator import BaseOperator

    from .models.task import BaseTask

logger = logging.getLogger("domino")


class DagFactory:
    """DAG Factory object."""

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
        "on_task_callbacks",
    )

    def validate_path(self, path: Path | str) -> Path:
        """Validate the path parameter that passing for generating Airflow DAG.

        Args:
            path (Path | str): Path to the DAG template folder.
        """
        path = path if isinstance(path, Path) else Path(path)

        # Path of DAG template should be directory
        if not path.is_dir():
            path = path.parent

        if (
            (dags_path := get_dags_path())
            and path != dags_path
            and not path.is_relative_to(dags_path)
        ):
            self.is_under_dags_dir = True
            logger.warning(
                f"⚠️ The template path: {path} is not under the Airflow "
                f"``dags_folder``, {dags_path}."
            )
        return path

    def __init__(
        self,
        path: Path | str,
        *,
        # Backend callbacks
        on_success_callback: list[Any] | None = None,
        on_failure_callback: list[Any] | None = None,
        on_task_callbacks: dict[str, Any] | None = None,
        # Backend assets
        python_callables: dict[str, Callable[..., None]] | None = None,
        task_objects: dict[str, BaseTask] | None = None,
        airflow_operators: dict[str, type[BaseOperator]] | None = None,
    ) -> None:
        """Initialize the DAG Generator.

        Args:
            path (Path | str): Path to the DAG template folder.
        """
        self.is_under_dags_dir = True
        self.path = self.validate_path(path=path)

        # Backend DAG callbacks
        self.on_success_callback = on_success_callback or []
        self.on_failure_callback = on_failure_callback or []

        # Backend task callbacks for specific tasks.
        self.on_task_callbacks = on_task_callbacks or {}

        # Backend assets for specific tasks.
        self.python_callables = python_callables or {}
        self.task_objects = task_objects or {}
        self.airflow_operators = airflow_operators or {}

        self.loader = DagLoader(self.path)
        self.conf: Dag | None = None

    @property
    def dag(self) -> Dag:
        """Return the DAG model from the DAG template."""
        dag: Dag | None = self.conf
        if dag is None:
            jinja_renderer = JinjaRender()
            data: dict[str, Any] = self.loader.read_dag()
            name: str = data["id"]
            try:
                dag: Dag = Dag.model_validate(
                    obj=data,
                    context={
                        "task_callbacks": self.on_task_callbacks,
                        "jinja_renderer": jinja_renderer,
                    },
                )
                self.conf = dag
                return dag
            except ValidationError:
                logger.exception(
                    f"❌ Validate Dag: {name!r}, failed with validation error"
                )
                raise
        return dag

    def build(self) -> DAG:
        """Build Airflow DAG object from the DAG model."""
        return self.dag.build()

    def build_airflow_dag_to_globals(self, gb: dict[str, Any]) -> None:
        """Build Airflow DAG to the globals.

        Args:
            gb (dict[str, Any]): The Global variables.
        """
        if get_bool_env(VAR_DOMINO_UNITTEST_MODE):  # pragma: no cov
            logger.warning(
                "⏭️ Skip for unittest environment from set the "
                "``DOMINO_UNITTEST_MODE`` variable."
            )
            return

        dag: DAG = self.build()
        gb[dag.dag_id] = dag

    def parse(self) -> dict[str, Any]:
        """Pre parsing the DAG template.

        Returns:
            dict[str, Any]: A DAG template data after passing all variables.
        """
        return self.dag.model_dump()
