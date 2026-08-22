from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Annotated, Literal, Union

from airflow.sdk.definitions.taskgroup import TaskGroup
from pydantic import Field

from ..const import MAX_THREADS_BUILD_TASK_GROUP
from ..providers import Register
from .builder import BaseAirflowTaskOrGroupBuilder

if TYPE_CHECKING:
    from airflow import DAG

    from .__types import BaseOperatorOrTaskGroup
    from .context import BuildContext


class Group(BaseAirflowTaskOrGroupBuilder):
    """Group Model."""

    id: str = Field(..., description="A unique identifier for the task group.")
    type: Literal["group"] = Field(
        default="group", description="The type of the task group."
    )
    desc: str = Field(
        default="",
        description="A task group description that will display on the UI.",
    )
    ui_color: str = Field(
        default="CornflowerBlue",
        description="The fill color of the TaskGroup node when displayed in the UI.",
    )
    ui_fgcolor: str = Field(
        default="#000",
        description="The label color of the TaskGroup node when displayed in the UI.",
    )

    tasks: list[TaskOrGroup] = Field(
        description="A list of Task or Group objects that belong to this group.",
    )

    def build(
        self,
        dag: DAG,
        build_context: BuildContext,
        task_group: TaskGroup | None = None,
    ) -> BaseOperatorOrTaskGroup:
        """Build Airflow TaskGroup instance.

        This method will start create Airflow TaskGroup instance and build all
        tasks inside this task group.

        Args:
            dag (DAG): An Airflow DAG object.
            task_group (TaskGroup, default None): An Airflow TaskGroup object
                if this task build under the task group.
            build_context (BuildContext, default None):
                A Context data that was created from the DAG Generator object.

        Returns:
            TaskGroup: An Airflow TaskGroup instance.
        """
        tg = TaskGroup(
            dag=dag,
            group_id=self.id,
            parent_group=task_group,
            tooltip=self.desc,
            ui_color=self.ui_color,
            ui_fgcolor=self.ui_fgcolor,
            # Disable ``default_args`` in TaskGroup level
            # default_args=None,
            # ⚠️ WARNING:
            #   Disable the ``prefix_group_id`` to avoid mapping downstream tasks
            #   to incorrect task ID.
            prefix_group_id=False,
            # ⚠️ WARNING: Disable ``add_suffix_on_collision`` to avoid confusion.
            #   Because we do not allow to set duplicate task ID in our model
            #   validation.
            add_suffix_on_collision=False,
        )

        # Start build tasks inside this task group mode.
        #   Move to use thread pool to speed up the building process.
        #   Use fail-fast strategy to stop immediately on first error.
        with ThreadPoolExecutor(MAX_THREADS_BUILD_TASK_GROUP) as executor:
            futures: list[Future] = [
                executor.submit(
                    task.backend_build,
                    dag=dag,
                    build_context=build_context,
                    task_group=tg,
                )
                for task in self.tasks
            ]
            try:
                for future in as_completed(futures):
                    future.result()
            except Exception:  # pragma: no cov
                # ⚠️ WARNING: Cancel remaining futures on first error
                for future in futures:
                    future.cancel()
                raise

            return tg


TaskOrGroup = Annotated[
    Union[
        Group,
        Register,
    ],
    Field(
        discriminator="type",
        description=(
            "A union of tasks and Group objects, allowing for polymorphic "
            "behavior based on the 'type' field."
        ),
    ),
]
