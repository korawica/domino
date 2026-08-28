from typing import Final

# For Airflow 3.+ compatibility.
from airflow.api_fastapi.common.types import UIAlert

DASHBOARD_UIALERTS: Final[list[UIAlert]] = [
    UIAlert(text="Welcome to Airflow Standalone Mode", category="warning"),
]
