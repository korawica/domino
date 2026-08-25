from airflow.sdk import TriggerRule
from pendulum import datetime

from domino.models.dag import Dag
from domino.renderer import JinjaRenderer
from domino.tasks import EmptyTask
from domino.utils import DotDict


def test_dag():
    dag = Dag.model_validate(
        obj={
            "id": "test_dag",
            "schedule": None,
            "start_date": "2026-01-01",
            "end_date": None,
            "catchup": False,
            "tasks": [
                {
                    "id": "start",
                    "type": "empty",
                },
                {
                    "id": "end",
                    "type": "empty",
                    "upstreams": ["start"],
                    "trigger_rule": "all_success",
                },
            ],
        }
    )
    assert dag.id == "test_dag"
    assert dag.schedule is None
    assert dag.start_date == datetime(2026, 1, 1, tz="UTC")
    assert dag.end_date is None
    assert dag.tasks == [
        EmptyTask(id="start"),
        EmptyTask(
            id="end", upstreams=["start"], trigger_rule=TriggerRule.ALL_SUCCESS
        ),
    ]
    assert dag.end_date is None
    assert dag.catchup is False
    assert len(dag.tasks) == 2
    assert dag.tasks[0].id == "start"
    assert dag.tasks[1].id == "end"


def test_dag_renderer():
    dag = Dag.model_validate(
        obj={
            "id": "test_dag",
            "schedule": None,
            "start_date": "{{ vars('start_date') }}",
            "end_date": "{{ vars('end_date', None) }}",
            "tasks": [],
        },
        context={
            "jinja_renderer": JinjaRenderer(
                user_defined_macros={
                    "vars": DotDict(start_date="2026-01-01").get_raise
                }
            )
        },
    )
    assert dag.start_date == datetime(2026, 1, 1, tz="UTC")
    assert dag.end_date is None
