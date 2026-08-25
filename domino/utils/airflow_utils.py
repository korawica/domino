from __future__ import annotations

from pathlib import Path

from airflow.configuration import conf
from airflow.sdk import Label

from domino.models.context import TaskContext


def get_airflow_version() -> tuple[int, int, int]:
    """Get the Airflow version as a tuple of integers.

    Returns:
        tuple[int, int, int]: The Airflow version.
    """
    from airflow import version

    versions = list(map(int, version.split(".")))
    return versions[0], versions[1], versions[2]


def get_dags_path() -> Path | None:
    """Get the Airflow DAGs folder path from the Airflow configuration.

    Returns:
        Path | None: The Airflow DAGs folder path.
    """
    path_str: str | None = conf.get("core", "dags_folder", fallback=None)
    if path_str:
        return Path(path_str)
    return None


def set_upstream_and_teardown(
    tasks: dict[str, TaskContext],
    label_sep_on_task_id: str = "::",
) -> None:  # NOSONAR
    """Set Upstream and Teardown Task for each tasks in mapping.

    Args:
        tasks (dict[str, TaskContext]): A mapping of task ID and TaskContext dict
            object.
        label_sep_on_task_id (str, optional): A separator string for the task ID
            to split the label from the task ID. Defaults to "::".
    """
    for task in tasks:
        task_mapped: TaskContext = tasks[task]

        # Set upstream task if it is defined in the template.
        if upstream := task_mapped["upstream"]:
            for t in upstream:
                try:
                    if label_sep_on_task_id in t:
                        t, label = t.split(
                            label_sep_on_task_id,
                            maxsplit=1,
                        )
                        if label:
                            task_mapped["task"].set_upstream(
                                tasks[t]["task"], edge_modifier=Label(label)
                            )
                            continue

                    # Default case without edge modifier
                    task_mapped["task"].set_upstream(tasks[t]["task"])
                except KeyError as e:
                    raise KeyError(
                        f"Task ids, {e}, does not found from the template.\n"
                        f"The current task key: {list(tasks.keys())}"
                    ) from e
        # Set setup & teardown task if it is defined in the template.
        if teardown := task_mapped.get("teardown"):
            try:
                task_mapped["task"].as_teardown(setups=tasks[teardown]["task"])
            except KeyError as e:
                raise KeyError(
                    f"Setups task id, {e}, does not found from the template.\n"
                    f"The current task key: {list(tasks.keys())}"
                ) from e
