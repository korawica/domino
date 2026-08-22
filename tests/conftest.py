import logging
import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv

if TYPE_CHECKING:
    from airflow.sdk.definitions.dag import DAG

# make_dotenv(Path(__file__).parent.parent)
load_dotenv(Path(__file__).parent.parent / ".env")


# Set unittest config for Airflow before importing Airflow modules.
os.environ["AIRFLOW_ENV"] = "dev"
os.environ["AIRFLOW__CORE__UNIT_TEST_MODE"] = "true"
os.environ["AIRFLOW__API__BASE_URL"] = "http://localhost:8080"

from domino.models.context import BuildContext  # noqa
from domino.models.label import Label  # noqa

# Prepare logging for external packages.
logging.getLogger("airflow.serialization.serde").setLevel(logging.WARNING)
logging.getLogger("airflow.models.variable").setLevel(logging.CRITICAL)
logging.getLogger("shapely.geos").setLevel(logging.WARNING)


@pytest.fixture(scope="package")
def test_path() -> Path:
    return Path(__file__).parent


@pytest.fixture(scope="package")
def root_path(test_path: Path) -> Path:
    return test_path.parent


@pytest.fixture(scope="package")
def dags_path(root_path: Path) -> Path:
    return root_path / "dags"


@pytest.fixture(scope="function")
def dag(test_path: Path) -> DAG:
    from airflow.sdk.definitions.dag import DAG

    return DAG(
        dag_id="test_tasks",
        start_date=datetime(2025, 1, 1),
        template_searchpath=str(test_path.absolute()),
        render_template_as_native_obj=True,
    )


@pytest.fixture(autouse=True)
def setup_airflow_dags_path(monkeypatch, root_path: Path) -> Iterator[None]:
    monkeypatch.setattr(
        "domino.generator.get_dags_path", lambda: root_path / "dags"
    )
    yield


@pytest.fixture(scope="function")
def build_context(test_path: Path) -> BuildContext:
    return BuildContext(
        path=test_path,
        loader=MagicMock(),
        vars={},
        tasks={},
        tools={},
        operators={},
        jinja_renderer=MagicMock(),
        python_callers={},
        label=Label(),
    )
