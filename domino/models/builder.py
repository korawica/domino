from abc import ABC, abstractmethod
from contextlib import nullcontext
from typing import TYPE_CHECKING, NotRequired, TypedDict, TypeVar

from airflow.sdk.bases.operator import BaseOperator
from airflow.sdk.definitions.taskgroup import TaskGroup
from pydantic import Field

from domino.models.templater import Templater

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG

    from domino.models.context import BuildContext


Operator = TypeVar("Operator", bound=BaseOperator)
OperatorOrTaskGroup = Operator | TaskGroup


class TaskContext(TypedDict):
    """Task Context dict typed."""

    task: OperatorOrTaskGroup
    upstream: list[str]
    teardown: NotRequired[str | None]


class BaseBuilder(Templater, ABC):
    """Base Builder Model."""

    id: str = Field(..., description="A unique identifier")

    @abstractmethod
    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> OperatorOrTaskGroup:
        """Tool building method for build any Airflow task object. This method
        can return Operator or TaskGroup object.

        Args:
            dag (DAG): An Airflow DAG object.
            build_context (BuildContext):
                A Context data that was created from the DAG Generator object.
            task_group (TaskGroup, optional): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            OperatorOrTaskGroup: This method can return depend on building
                logic that already pass the DAG instance from the parent.
        """
        raise NotImplementedError(
            "This Builder object should implement build method."
        )


class BaseTaskOrGroup(BaseBuilder, ABC):
    """Base Task or Group Model."""

    desc: str | None = Field(
        default=None,
        description=(
            "A task or task group description. This value will pass "
            "to the ``doc`` parameter of the Airflow Operator or Airflow "
            "TaskGroup."
        ),
    )
    upstream: list[str] = Field(
        default_factory=list, description="A list of upstream task IDs"
    )

    def backend_build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> OperatorOrTaskGroup:
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
                A Context data that was created from the DAG Generator object.
            task_group (TaskGroup, default None): An Airflow TaskGroup object
                if this task build under the task group.

        Returns:
            OperatorOrTaskGroup: An Airflow Operator or TaskGroup instance.
                - Operator: Be a basic task that should implement 1-1 with Airflow
                            Operator.
                - TaskGroup: Be note that if you implement TaskGroup model, it will
                             return TaskGroup instance, and you should implement
                             task dependencies by yourself inside the TaskGroup model.
        """

        # Start call build the Airflow object from the `build` method.
        task_airflow: OperatorOrTaskGroup = self.build(
            dag=dag,
            task_group=task_group,
            build_context=build_context,
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
        lock_cm = (
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
                "upstream": self.upstream,
                "teardown": teardown,
                "task": task_airflow,
            }

        return task_airflow
