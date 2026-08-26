from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..utils import remove_system_fields

logger = logging.getLogger("domino.variable")


class Variable(BaseModel):
    """Variable model."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["variable"] = "variable"
    stages: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="A dictionary of stages and their corresponding variables.",
    )

    @classmethod
    def pull_stage(
        cls,
        path: Path,
        env: str | None = None,
    ) -> dict[str, Any]:
        """Pull variables for a specific stage from the given path.

        Args:
            path (Path): Path of the variable file.
            env (str, optional): A variable environment. If not provided, it will use the
                current environment from the environment variable.

        Returns:
            dict[str, Any]: A dictionary of variables for the specified stage.
        """
        from ..loader import read_variables
        from ..utils import get_current_env

        return cls.model_validate(
            obj=remove_system_fields(read_variables(path=path))
        ).stages.get(env or get_current_env(), {})

    @classmethod
    def global_variables(
        cls,
        path: Path,
        env: str | None = None,
        stop_path: Path | None = None,
        max_depth: int = 2,
    ) -> dict[str, Any]:
        """Pull recursively global variables from the given path until
        ``stop_path`` or ``max_depth`` is reached.

        Args:
            path (Path): Path of the variable file.
            env (str, optional): A variable environment. If not provided, it will use the
                current environment from the environment variable.
            stop_path (Path, optional): The path to stop the recursive search.
            max_depth (int, optional): The maximum depth to search for global variables.

        Returns:
            dict[str, Any]: A dictionary of global variables.
        """
        variables: dict[str, Any] = {}

        # NOTE: Calculate ``stop_path`` from ``max_depth`` if not set.
        if stop_path and stop_path == path:
            logger.warning(
                "⚠️ The ``stop_path`` is equal to path, so return empty variables."
            )
            return variables

        if max_depth <= 0:
            raise ValueError("A ``max_depth`` must be greater than 0.")

        if len(path.parents) == 0:
            logger.warning(
                f"⚠️ The path: {path} does not have any parent, so return empty "
                f"variables."
            )
        elif (
            not stop_path or (stop_path and stop_path not in path.parents)
        ) and max_depth > 0:
            if stop_path and stop_path not in path.parents:
                logger.warning(
                    f"⚠️ The ``stop_path``: {stop_path} is not in the parents of "
                    f"path: {path}. So, it will recursively search util "
                    f"``max_depth``."
                )
            stop_path = path
            for _ in range(max_depth):
                if stop_path == stop_path.parent:
                    break
                stop_path = stop_path.parent

        for p in path.parents:
            try:
                logger.debug("🔍 Try to pull Global Variable at: %s", p)
                data: dict[str, Any] = Variable.pull_stage(path=p, env=env)
            except (OSError, ValueError, TypeError) as err:
                # NOTE: Ignore these exceptions and continue to the upper path.
                #  - OSError: Global variable file does not exist or permission.
                #  - ValueError: Global variable file has empty content.
                #  - TypeError: Global variable file has invalid content type.
                logger.debug(
                    "⏭️ Global Variable did not found or it has some problem on "
                    "the content excluded parser at template path: %s",
                    p,
                )
                logger.debug("⏭️ Exception: %s", err)
                data = {}

            # WARNING: Later variables will override earlier ones.
            variables = data | variables

            if p == stop_path:
                break

        return variables
