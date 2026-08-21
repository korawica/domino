from pathlib import Path

from airflow.configuration import conf


def get_dags_path() -> Path | None:
    """Get the Airflow DAGs folder path from the Airflow configuration.

    Returns:
        str: The Airflow DAGs folder path.
    """
    path_str: str | None = conf.get("core", "dags_folder", fallback=None)
    if path_str:
        return Path(path_str)
    return None
