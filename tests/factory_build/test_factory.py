import shutil
from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent

import pytest
from airflow import DAG

from domino.factory import DagFactory


@pytest.fixture(scope="module")
def mock_dag_path(dags_path: Path) -> Iterator[Path]:
    mock_dag_path = dags_path / "mock_dag_simple"
    mock_dag_path.mkdir(parents=True, exist_ok=True)
    with (mock_dag_path / "dag.yml").open(mode="w", encoding="utf-8") as f:
        f.write(
            dedent(
                """
                id: example
                type: dag
                docs: docs.md
                owners: ["whoami@email.com"]
                tasks:
                  - id: start
                    type: empty

                  - id: end
                    type: empty
                    upstreams: [start]
                    trigger_rule: all_success
                """.lstrip("\n")
            )
        )

    with (mock_dag_path / "docs.md").open(mode="w", encoding="utf-8") as f:
        f.write(
            dedent(
                """
                # Example DAG

                This is an example DAG for testing purposes.
                """.lstrip("\n")
            )
        )

    yield mock_dag_path

    shutil.rmtree(mock_dag_path, ignore_errors=True)


def test_dag_factory_build(mock_dag_path: Path):
    factory = DagFactory(path=mock_dag_path)
    dag: DAG = factory.build()
    assert dag.dag_id == "example"
    assert dag.start_date is None
    assert dag.end_date is None
    assert dag.owner == "whoami@email.com"
