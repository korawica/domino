# Airflow Dockerfile - constraint file mode
ARG PYTHON_VERSION=3.11
ARG ROCKYLINUX_VERSION=9.3
FROM rockylinux:${ROCKYLINUX_VERSION} AS builder

# Install OS packages
#   - gcc: For CPython package compilation
#   - libpq-devel: Postgres relate package
RUN dnf install -y  \
      gcc \
      libpq-devel \
    && dnf clean all

ENV UV_COMPILE_BYTECODE=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /uvx /bin/

ARG PYTHON_VERSION=3.11
RUN uv venv /opt/venv --python=${PYTHON_VERSION}

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /opt

# Install the base version
ARG AIRFLOW_VERSION=2.11.2

# Use the custom constraints file instead of the official one to avoid
#   dependency conflict.
#   For the official constraints file, see:
#   "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
COPY .airflow-assets/constraints/airflow${AIRFLOW_VERSION}-python${PYTHON_VERSION}.txt ./

# ⚠️ WARNING: Do NOT run `uv sync` here. The project pyproject.toml declares
#   `apache-airflow>=2.11.1,<4.0.0` in its base dependencies, and the lockfile
#   resolves that to Airflow 3.2.0. If we sync first and then `uv pip install`
#   the target 2.11.x version on top, the downgrade leaves orphan files from
#   Airflow 3.x behind in site-packages (notably 3.x-only Alembic migration
#   scripts under `airflow/migrations/versions/`), which Alembic then tries to
#   import at `airflow db init` time and fails with:
#     ImportError: cannot import name 'ignore_sqlite_value_error'
#       from 'airflow.migrations.utils'
#   Instead we install the exact target Airflow version directly, together
#   with the runtime deps the `domino` package imports (mounted as a volume,
#   not installed here), all pinned by the version-specific constraints file.
RUN uv pip install \
    "apache-airflow==${AIRFLOW_VERSION}" \
    "apache-airflow-providers-cncf-kubernetes" \
    "apache-airflow-providers-google" \
    "apache-airflow-providers-postgres" \
    "apache-airflow-providers-opsgenie" \
    "apache-airflow-providers-http" \
    "apache-airflow-providers-airbyte" \
    "apache-airflow-providers-openlineage" \
    "fastavro" \
    "pydantic" \
    "python-dotenv" \
    --constraint ./airflow${AIRFLOW_VERSION}-python${PYTHON_VERSION}.txt \
  && find /opt/venv -type d -name '__pycache__' -exec rm -rf {} + \
  && rm -rf ~/.cache /root/.cache /tmp/*

ENV PYTHONPATH="/opt/airflow:${PYTHONPATH}"

WORKDIR /opt/airflow
