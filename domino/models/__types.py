from airflow.sdk.bases.operator import BaseOperator
from airflow.sdk.definitions.taskgroup import TaskGroup

BaseOperatorOrTaskGroup = BaseOperator | TaskGroup
