from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import nullcontext
from typing import TYPE_CHECKING

from airflow.sdk.bases.operator import BaseOperator
from airflow.sdk.definitions.taskgroup import TaskGroup
from pydantic import ConfigDict, Field

from .__types import BaseOperatorOrTaskGroup
from .templater import Templater

if TYPE_CHECKING:
    from threading import Lock

    from airflow.sdk.definitions.dag import DAG

    from .context import BuildContext, TaskContext


class DominoBuilderMixin(ABC):
    @abstractmethod
    def build(self, build_context: BuildContext) -> None:
        """Object building method for any builder object.

        Args:
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
        """
        raise NotImplementedError(
            "This Builder object should implement build method."
        )


class AirflowBuilderMixin(ABC):
    @abstractmethod
    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Tool building method for build any Airflow task object. This method
        can return Operator or TaskGroup object.

        Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: This method can return depend on building
                logic that already pass the DAG instance from the parent.
        """
        raise NotImplementedError(
            "This Builder object should implement build method."
        )


class BaseAirflowBuilder(Templater, AirflowBuilderMixin, ABC):
    """Base Builder Model."""

    # It should not allow to add extra fields
    model_config = ConfigDict(extra="forbid")


class BaseAirflowTaskOrGroupBuilder(BaseAirflowBuilder, ABC):
    """Base Airflow Task or TaskGroup Builder Model."""

    id: str = Field(..., description="A unique identifier")
    desc: str | None = Field(
        default=None,
        description="A task or task group description.",
    )
    upstreams: list[str] = Field(
        default_factory=list,
        description="A list of upstream task IDs",
    )

    def backend_build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Backend Building the Airflow Operator or TaskGroup object.

        This method will update tasks building context value before returning
        result from building.

        Steps:
        1. Build the Airflow Operator or TaskGroup object from this model.
        2. Validate built instance result
        3. Update the tasks building context value with the built instance
           result with its ID, upstream, and teardown

        Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Factory object.
            task_group (TaskGroup, default None): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            BaseOperatorOrTaskGroup: An Airflow Operator or TaskGroup instance.
        """

        # Start call build the Airflow object from the `build` method.
        task_airflow: BaseOperatorOrTaskGroup = self.build(
            dag=dag,
            build_context=build_context,
            task_group=task_group,
        )

        if not isinstance(task_airflow, (BaseOperator, TaskGroup)):
            raise NotImplementedError(
                f"The build method must return any Airflow Operator that "
                f"inherit from ``BaseOperator`` or ``TaskGroup`` instance, but got "
                f"{type(task_airflow)}."
            )

        tasks: dict[str, TaskContext] | None = build_context.get("tasks")
        if tasks is None:
            return task_airflow

        # Support for duplicate ID for mapping upstream.
        teardown: str | None = None
        if isinstance(task_airflow, TaskGroup):
            _id: str = task_airflow.group_id or self.id
        else:
            _id: str = task_airflow.task_id

            # Using getattr because task group model do not implement
            #   `teardown` field.
            teardown = getattr(self, "teardown", None)

        # Use lock context manager to prevent race condition when building
        #   tasks in parallel. This is important for thread safety when multiple
        #   threads are building tasks and accessing the shared `tasks`
        #   dictionary.
        lock_cm: Lock | nullcontext = (
            build_context["tasks_lock"]
            if build_context and "tasks_lock" in build_context
            else nullcontext()
        )
        with lock_cm:
            if _id in tasks:
                raise NotImplementedError(
                    f"Task ID was duplicate: {_id}. This template should "
                    f"not allow to set the same ID because it force disable "
                    f"``prefix_group_id`` and ``add_suffix_on_collision``."
                )

            tasks[_id] = {
                "upstreams": self.upstreams,
                "teardown": teardown,
                "task": task_airflow,
            }

        return task_airflow
