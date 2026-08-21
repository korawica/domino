import logging
from pathlib import Path

from .utils import get_dags_path

logger = logging.getLogger("domino")


class DagGenerator:
    """DAG Generator object."""

    def __init__(
        self,
        path: Path | str,
    ) -> None:
        """Initialize the DAG Generator.

        Args:
            path (Path | str): Path to the DAG template folder.
        """
        self.path = path if isinstance(path, Path) else Path(path)
        if (
            (dags_path := get_dags_path())
            and self.path != dags_path
            and dags_path not in self.path.parents
        ):
            logger.warning(
                f"⚠️ The template path: {self.path} is not under the Airflow "
                f"``dags_folder``, {dags_path}."
            )
