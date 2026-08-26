from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from .const import VAR_DOMINO_UNITTEST_MODE
from .loader import DagLoader
from .models.context import BuildContext
from .models.dag import Dag
from .models.label import Label
from .renderer import JinjaRenderer
from .utils import DotDict, cached_method, get_bool_env, get_dags_path

if TYPE_CHECKING:
    from airflow import DAG
    from airflow.sdk.bases.operator import BaseOperator

    from .models.task import BaseTask

logger = logging.getLogger("domino")


class DagFactory:
    """DAG Factory object."""

    __slots__ = (
        "path",
        "use_airflow_variable",
        "is_under_dags_dir",
        "loader",
        "conf",
        "on_success_callback",
        "on_failure_callback",
        "python_callables",
        "task_objects",
        "airflow_operators",
        "on_task_callbacks",
        "user_defined_macros",
        "user_defined_filters",
        "template_searchpath",
        "_jinja_renderer",
        "_pull_vars_cache",
    )

    def __init__(
        self,
        path: Path | str,
        *,
        use_airflow_variable: bool = False,
        # Backend callbacks
        on_success_callback: list[Any] | None = None,
        on_failure_callback: list[Any] | None = None,
        on_task_callbacks: dict[str, Any] | None = None,
        # Backend assets
        python_callables: dict[str, Callable[..., None]] | None = None,
        task_objects: dict[str, BaseTask] | None = None,
        airflow_operators: dict[str, type[BaseOperator]] | None = None,
        # Jinja environment
        user_defined_macros: dict[str, Callable[..., Any]] | None = None,
        user_defined_filters: dict[str, Callable[..., Any]] | None = None,
        template_searchpath: list[str] | None = None,
    ) -> None:
        """Initialize the DAG Factory.

        Args:
            path (Path | str): Path to the DAG template folder.
        """
        self.is_under_dags_dir = True
        self.path = self.validate_path(path=path)
        self.use_airflow_variable = use_airflow_variable

        # Backend DAG callbacks
        self.on_success_callback = on_success_callback or []
        self.on_failure_callback = on_failure_callback or []

        # Backend task callbacks for specific tasks.
        self.on_task_callbacks = on_task_callbacks or {}

        # Backend assets for specific tasks.
        self.python_callables = python_callables or {}
        self.task_objects = task_objects or {}
        self.airflow_operators = airflow_operators or {}

        self.user_defined_macros = user_defined_macros or {}
        self.user_defined_filters = user_defined_filters or {}

        self.template_searchpath: list[str] = [
            # NOTE: Remove resolve for fixing GitSync change hash path.
            # str(p.resolve().absolute())
            str(p.absolute()) if isinstance(p, Path) else p
            for p in (template_searchpath or [])
        ] + [str(self.path.absolute()), str((self.path / "assets").absolute())]

        self.loader = DagLoader(self.path)
        self.conf: Dag | None = None

        # Cache the JinjaRenderer object to avoid re-rendering the template
        #   fields multiple times.
        self._jinja_renderer: JinjaRenderer | None = None

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

    @cached_method(ttl=60)
    def pull_vars(self, name: str, env: str | None = None) -> dict[str, Any]:
        """Pull Variable for the current template config DAG name.

        This method will pull global variable first before pull variable
        from the variable file.

        Args:
            name (str): A variable name.
            env (str, optional): A variable environment. If not provided, it will use the
                current environment from the environment variable.

        Returns:
            dict[str, Any]: A variable mapping.
        """
        from .loader import read_airflow_variables

        # from .models.global_variable import pull_global_vars
        from .models.variable import Variable
        from .utils import get_current_env

        env: str = env or get_current_env()

        # read Airflow variable
        if self.use_airflow_variable:
            airflow_vars = read_airflow_variables(name=name)
        else:
            airflow_vars = {}

        return (
            Variable.global_variables(
                self.path,
                stop_path=get_dags_path(),
                env=env,
            )
            | Variable.pull_stage(path=self.path, env=env)
            | airflow_vars
        )

    @property
    def dag(self) -> Dag:
        """Return the DAG model from the DAG template."""
        dag: Dag | None = self.conf
        if dag is None:
            data: dict[str, Any] = self.loader.read_dag()
            name: str = data["id"]

            # ???

            try:
                dag: Dag = Dag.model_validate(
                    obj=data,
                    context={
                        "task_callbacks": self.on_task_callbacks,
                        "jinja_renderer": self.jinja_renderer,
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

    @property
    def jinja_renderer(self) -> JinjaRenderer:
        """Return the JinjaRenderer object from the DAG model."""
        jinja_renderer: JinjaRenderer | None = self._jinja_renderer
        if jinja_renderer is None:
            jinja_renderer: JinjaRenderer = JinjaRenderer(
                user_defined_macros=self.user_defined_macros,
                user_defined_filters=self.user_defined_filters,
                template_searchpath=self.template_searchpath,
            )
            self._jinja_renderer = jinja_renderer
        return jinja_renderer

    def build(
        self,
        *,
        user_defined_macros: dict[str, Callable[..., Any]] | None = None,
        user_defined_filters: dict[str, Callable[..., Any]] | None = None,
    ) -> DAG:
        """Build Airflow DAG object from the DAG model.

        Args:
            user_defined_macros (dict[str, Callable[..., Any]] | None): A dictionary
                of user-defined macros to be used in the DAG.
            user_defined_filters (dict[str, Callable[..., Any]] | None): A dictionary
                of user-defined filters to be used in the DAG.

        Returns:
            DAG: An Airflow DAG instance.
        """
        renderer = self.jinja_renderer
        user_defined_macros: dict[str, Any] = (
            self.user_defined_macros
            | {"vars": DotDict(self.pull_vars(name=self.dag.id)).get_raise}
            | (user_defined_macros or {})
        )
        renderer.env.globals.update(user_defined_macros)

        build_context: BuildContext = {
            "path": self.path,
            "tasks": {},
            "tasks_lock": threading.Lock(),
            "label": Label(),
            "jinja_renderer": renderer,
            "task_objects": self.task_objects,
            "airflow_operators": self.airflow_operators,
            "python_callables": self.python_callables,
        }
        return self.dag.build(
            build_context=build_context,
            template_searchpath=None,
            user_defined_macros=user_defined_macros,
            user_defined_filters=user_defined_filters,
            jinja_environment_kwargs=None,
        )

    def build_airflow_dag_to_globals(
        self,
        gb: dict[str, Any],
        *,
        user_defined_macros: dict[str, Callable[..., Any]] | None = None,
        user_defined_filters: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        """Build Airflow DAG to the globals.

        Args:
            gb (dict[str, Any]): The Global variables.
            user_defined_macros (dict[str, Callable[..., Any]] | None): A dictionary
                of user-defined macros to be used in the DAG.
            user_defined_filters (dict[str, Callable[..., Any]] | None): A dictionary
                of user-defined filters to be used in the DAG.
        """
        if get_bool_env(VAR_DOMINO_UNITTEST_MODE):  # pragma: no cov
            logger.warning(
                "⏭️ Skip for unittest environment from set the "
                "``DOMINO_UNITTEST_MODE`` variable."
            )
            return

        dag: DAG = self.build(
            user_defined_macros=user_defined_macros,
            user_defined_filters=user_defined_filters,
        )
        gb[dag.dag_id] = dag

    def parse(self) -> dict[str, Any]:
        """Pre parsing the DAG template.

        Returns:
            dict[str, Any]: A DAG template data after passing all variables.
        """
        return self.dag.model_dump()
