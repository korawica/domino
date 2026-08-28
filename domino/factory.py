from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from airflow.sdk.definitions._internal.templater import (  # noqa
    FILTERS as AIRFLOW_FILTERS,
)
from pydantic import ValidationError

from .const import VAR_DOMINO_UNITTEST_MODE
from .models.context import BuildContext
from .models.dag import Dag
from .models.label import Label
from .renderer import JinjaRenderer
from .utils import (
    DotDict,
    cached_method,
    change_tz,
    date_add,
    format_dt,
    get_bool_env,
    get_dags_path,
    remove_system_fields,
    to_bkk,
    to_utc,
)

if TYPE_CHECKING:
    from airflow import DAG
    from airflow.sdk.bases.operator import BaseOperator

    from .models.task import BaseTask

logger = logging.getLogger("domino")


FILTERS: Final[dict[str, Callable]] = {
    "tz": change_tz,
    "fmt": format_dt,
    "date_add": date_add,
    "bkk": to_bkk,
    "utc": to_utc,
    **AIRFLOW_FILTERS,
}


class DagFactory:
    """DAG Factory object."""

    __slots__ = (
        "path",
        "use_airflow_variable",
        "is_under_dags_dir",
        "conf",
        "on_success_callbacks",
        "on_failure_callbacks",
        "python_callables",
        "task_objects",
        "airflow_operators",
        "on_task_callbacks",
        "user_defined_macros",
        "user_defined_filters",
        "template_searchpath",
        "_jinja_renderer",
        # cached variable from `pull_vars` method
        "_pull_vars_cache",
    )

    def __init__(
        self,
        path: Path | str,
        *,
        use_airflow_variable: bool = False,
        # Backend callbacks
        on_success_callbacks: list[Any] | None = None,
        on_failure_callbacks: list[Any] | None = None,
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
        self.on_success_callbacks = on_success_callbacks or []
        self.on_failure_callbacks = on_failure_callbacks or []

        # Backend task callbacks for specific tasks.
        self.on_task_callbacks = on_task_callbacks or {}

        # Backend assets for specific tasks.
        self.python_callables = python_callables or {}
        self.task_objects = task_objects or {}
        self.airflow_operators = airflow_operators or {}

        self.user_defined_macros = user_defined_macros or {}
        self.user_defined_filters = FILTERS | (user_defined_filters or {})

        self.template_searchpath: list[str] = [
            # NOTE: Remove resolve for fixing GitSync change hash path.
            # str(p.resolve().absolute())
            str(p.absolute()) if isinstance(p, Path) else p
            for p in (template_searchpath or [])
        ] + [str(self.path.absolute()), str((self.path / "assets").absolute())]

        self.conf: Dag | None = None

        # Cache the JinjaRenderer object to avoid re-rendering the template
        #   fields multiple times.
        self._jinja_renderer: JinjaRenderer | None = None

    def validate_path(self, path: Path | str) -> Path:
        """Validate the path parameter that passing for generating Airflow DAG.

        Args:
            path (Path | str): Path to the DAG template folder.

        Returns:
            Path: A validated path that is under the Airflow ``dags_folder``.
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
        from .models.variable import Variable
        from .utils import get_current_env

        env: str = env or get_current_env()
        return (
            Variable.global_variables(
                path=self.path,
                stop_path=get_dags_path(),
                env=env,
            )
            | Variable.pull_stage(path=self.path, env=env)
            | (
                read_airflow_variables(name=name)
                if self.use_airflow_variable
                else {}
            )
        )

    @property
    def dag(self) -> Dag:
        """Return the DAG model from the DAG template."""
        dag: Dag | None = self.conf
        if dag is None:
            from .loader import read_dag

            data: dict[str, Any] = remove_system_fields(read_dag(self.path))
            name: str = data["id"]
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
            user_defined_macros (dict[str, Callable[..., Any]] | None):
                An override dictionary of user-defined macros to be used in
                the DAG.
            user_defined_filters (dict[str, Callable[..., Any]] | None):
                An override dictionary of user-defined filters to be used in
                the DAG.

        Returns:
            DAG: An Airflow DAG instance.
        """
        renderer = self.jinja_renderer
        user_defined_macros: dict[str, Any] = (
            self.user_defined_macros
            | {
                "vars": DotDict(self.pull_vars(name=self.dag.id)).get_raise,
                "env": os.getenv,
            }
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
            on_success_callbacks=self.on_success_callbacks,
            on_failure_callbacks=self.on_failure_callbacks,
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

        It allows to skip building the DAG when the ``DOMINO_UNITTEST_MODE``
        environment variable is set to True.

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

    def parse(
        self,
        # user_defined_macros: dict[str, Callable[..., Any]] | None = None,
        # user_defined_filters: dict[str, Callable[..., Any]] | None = None,
    ) -> dict[str, Any]:
        """Pre parsing the DAG template.

        Returns:
            dict[str, Any]: A DAG template data after passing all variables.
        """
        return self.dag.model_dump(
            exclude_unset=True,
        )
