from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from airflow.sdk.definitions.variable import Variable as AirflowVariable
from airflow.sdk.exceptions import AirflowRuntimeError
from yaml import safe_load
from yaml.constructor import ConstructorError
from yaml.parser import ParserError

logger = logging.getLogger("domino.loader")


def extract_yaml(file: Path) -> tuple[str, dict[str, Any] | list[Any]]:
    """Extract YAML content from file.

    Args:
        file (Path): A YAML file path.

    Returns:
        tuple[str, dict[str, Any] | list[Any]]: A pair of the raw content
            and its parsed data as a Python object.
    """
    try:
        raw_data: str = file.read_text(encoding="utf-8")
        data: dict[str, Any] | list[Any] = safe_load(raw_data)
    except ParserError:
        logger.error(f"🚨 YAML file, {file}, can not parsing")
        raise
    except ConstructorError:
        logger.error(f"🚨 YAML file, {file}, got constructor error")
        raise
    except Exception as e:  # pragma: no cov
        logger.error(
            f"🚨 YAML file got error from safe loading without handle, "
            f"{e.__class__.__name__} {e}, {file}"
        )
        raise
    return raw_data, data


def read_yaml_conf(  # NOSONAR
    path: Path,
    conf_type: tuple[str, ...],
    prefix_pattern: str,
    id_key: str | None = None,
    only_one_conf: bool = False,
    pre_validate: Callable | None = None,
    include_raw_content: bool = True,
    max_threads: int = 2,
    recursive: bool = True,
) -> list[dict[str, Any]]:
    """Read Conf data from the path argument.

    Args:
        path (Path): A path that use for searching config file.
        id_key (str): An ID key checking in the config data.
        conf_type (tuple[str, ...]): A tuple of type value that checking in
            the config data.
        prefix_pattern (str): A file pattern for searching files in the conf path.
        only_one_conf (bool): A flag for checking the conf data should contain
            only one config data or not.
        pre_validate (Callable | None): A function that checks the conf data
            before returning the result data. It will raise an error if the
            conf data does not pass the validation step.
        include_raw_content (bool, default True): Add the raw data or not.
        max_threads (int, default 2): A maximum number of threads for reading
            the config files. It should be greater than 0.
        recursive (bool, default True): Whether recursively read the config
            files or not.

    Raises:
        ValidationError:
            If the pre-validate flag is enabled and the DAG template data
            does not pass the validation step.
        ValueError:
            If the ``only_one_conf`` flag is enabled and the fetched DAG
            template data more than one.

    Returns:
        list[dict[str, Any]]: A list of conf data after validate step.
    """

    def _extract(file: Path) -> dict[str, Any] | None:
        """Internal extract YAML content from file and validate the data.

        Args:
            file (Path): A path that use for searching config file.
        """
        logger.debug(f"💡 Get Object: {file}")
        try:
            raw_data, data = extract_yaml(file=file)
        except ParserError:
            return None

        if not data or isinstance(data, list):
            logger.warning(
                f"⚠️ Skip template file that does not contain any content "
                f"or list of config, file: {file}."
            )
            return None

        if (id_key and id_key not in data) or data.get(
            "type", "NOTSET"
        ) not in conf_type:
            logger.warning(
                f"⚠️ Skip template file that does not contain valid type or "
                f"ID key, file: {file}."
            )
            return None

        file_stats = file.stat()
        model: dict[str, Any] = {
            "__filename": file.name,
            "__parent_dir": file.parent,
            "__created_dt": file_stats.st_ctime,
            "__updated_dt": file_stats.st_mtime,
            # ⏭️ NOTE: Remove hash for reduce parsing performance impact.
            # "raw_data_hash": hash_sha256(raw_data),
            **data,
        }
        if include_raw_content:
            model["__raw_data"] = raw_data

        if id_key:
            logger.info(f"⚙️ Load Conf ID: {model[id_key]!r}")

        if pre_validate is not None:
            try:
                pre_validate(model)
            except Exception:
                raise

        return model

    glob_func = path.rglob if recursive else path.glob
    files: list[Path] = [
        f
        for f in glob_func(f"{prefix_pattern}.y*ml")  # noqa
        if f.name.endswith((".yml", ".yaml"))
    ]

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        conf: list[dict[str, Any]] = [
            r for r in executor.map(_extract, files) if r is not None
        ]

    if not conf:
        logger.warning(
            "⚠️ Read config file from this template path does not exists"
        )
    elif only_one_conf and len(conf) > 1:
        logger.error(
            f"🚨 Conf data should contain only one per folder:\n{conf}."
        )
        raise ValueError("Conf data should contain only one per folder.")
    return conf


class DagLoader:
    """DAG Loader object.

    This object using for loading the DAG template file and return the Dag model.
    """

    __slots__ = ("path",)

    def __init__(self, path: Path) -> None:
        self.path = path

    def read_dag(self) -> dict[str, Any]:
        """Read the DAG template file and return the data that already read via
        YAML parser.
        """
        conf: list[dict[str, Any]] = read_yaml_conf(
            path=self.path,
            id_key="id",
            conf_type=("dag",),
            prefix_pattern="dag",
            only_one_conf=False,
        )
        return next(
            iter(
                sorted(
                    conf,
                    key=lambda x: x.get("__filename", "__old"),
                    reverse=True,
                )
            ),
            {},
        )


def read_variables(path: Path) -> dict[str, Any]:
    """Read variables file and return the data that already read via YAML
    parser.

    Args:
        path (Path): A path that use for searching config file.
    """
    conf: list[dict[str, Any]] = read_yaml_conf(
        path=path,
        conf_type=("variable",),
        prefix_pattern="variables",
        only_one_conf=False,
        recursive=False,
    )
    return next(
        iter(
            sorted(
                conf,
                key=lambda x: x.get("__filename", "__old"),
                reverse=True,
            )
        ),
        {},
    )


def read_airflow_variables(name: str) -> dict[str, Any]:
    """Read Airflow Variable and return the data that already read via YAML
    parser.

    Examples:

        ```text
        # Airflow Variable: my_variable
        key1: value1
        key2:
          nested_key:
            value: [1, 2, 3]
        ```
    """
    airflow_vars: dict[str, Any] = {}
    try:
        raw_var: str = AirflowVariable.get(name, deserialize_json=False)
        logger.debug("Pull Variable from Airflow: %s", name)
        logger.debug("Raw Variable Content: %s", raw_var)
        airflow_vars: dict[str, Any] = safe_load(raw_var)
    except AirflowRuntimeError as err:  # pragma: no cov
        # NOTE: Raise from Airflow version >= 3.0.0 instead of KeyError.
        logger.error(f"🚨 Airflow 3.0 Variable Error: {err}")
    except Exception as err:  # pragma: no cov
        logger.error(
            "🚨 Pull Variable from Airflow get some unexpected error: %s",
            err,
        )
    return airflow_vars
