# Domino

Lightweight **YAML Template** for [Apache Airflow](https://airflow.apache.org/) that
focus on the Data Engineering team to build and maintain DAGs of Data Pipeline
in a more efficient way.

Folder structure for a DAG that want to create by Domino.

```txt
dags/
  your_dag/
    ├── operators/
    │   ├── __init__.py
    │   └── <operator_name>.py
    ├── __init__.py
    ├── dag.yml
    ├── docs.md
    └── variables.yml
```

Core DAG Backend between Airflow DAG object and YAML template.

```py
from domino.factory import DagFactory
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

factory = DagFactory(
    path=__path__,
    airflow_operators={"bq_insert_job": BigQueryInsertJobOperator},
)
factory.build_airflow_dag_to_globals(globals())
```

Move writing DAG from Python to YAML template.

```yml
id: seeing_dag
type: dag
desc: Exploration data from BigQuery
docs: docs.md
owners: [whoami@email.com]
labels:
  team: data-analytics
  system: data-platform
  priority: vary-low
tags:
  - domino
  - bigquery

schedule: "10 0 * * *"
start_date: "2023-01-01T00:00:00Z"
end_date: "{{ vars('end_date') }}"
catchup: "{{ vars('catchup') }}"
max_active_runs: 1
max_active_tasks: 5
tasks:
  - id: start
    type: empty

  - id: process
    type: operator
    upstreams: ["start"]
    inputs:
      airflow_operator: bq_insert_job
      op_kwargs:
        configuration:
          query:
            query: "SELECT * FROM `{{ vars('project_id') }}.dataset.table`"
            useLegacySql: false

  - id: end
    type: empty
    upstreams: ["process"]
    trigger_rule: all_done
```

Dynamic variables with different values, set `DOMINO_ENV` for dynamic pickup.

```yml
type: variable
stages:
  dev:
    end_date: "2023-12-31T00:00:00Z"
    catchup: false
    project_id: "your-dev-project-id"
  prod:
    end_date: null
    catchup: true
    project_id: "your-prod-project-id"
```
