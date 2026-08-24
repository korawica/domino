from __future__ import annotations

from typing import Union

from airflow.sdk.bases.operator import BaseOperator
from airflow.sdk.definitions.taskgroup import TaskGroup

BaseOperatorOrTaskGroup = Union[BaseOperator, TaskGroup]
