from typing import TypeVar

from airflow.sdk.bases.operator import BaseOperator
from airflow.sdk.definitions.taskgroup import TaskGroup

Operator = TypeVar("Operator", bound=BaseOperator)
OperatorOrTaskGroup = Operator | TaskGroup
