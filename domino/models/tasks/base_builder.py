from abc import ABC, abstractmethod
from typing import Any

from pydantic import Field

from ..templater import Templater


class BaseBuilder(Templater, ABC):
    """Base Builder Model."""

    @abstractmethod
    def build(
        self,
        dag: Any,
        build_context: Any,
        task_group: Any | None = None,
    ) -> Any:
        """Tool building method for build any Airflow task object. This method
        can return Operator or TaskGroup object.

        Args:
            dag (DAG): An Airflow DAG object.
            task_group (TaskGroup, default None): An Airflow TaskGroup object
                if this task build under the task group.
            build_context (BuildContext, default None):
                A Context data that was created from the DAG Generator object.

        Returns:
            Operator | TaskGroup: This method can return depend on building
                logic that already pass the DAG instance from the parent.
        """
        raise NotImplementedError(
            "This Builder object should implement build method."
        )


class BaseTaskOrGroup(BaseBuilder, ABC):
    id: str = Field(
        ..., description="A unique identifier for the task or group."
    )
