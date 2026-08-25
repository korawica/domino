# Domino

Lightweight **YAML Template** for [Apache Airflow](https://airflow.apache.org/) that
focus on the Data Engineering team to build and maintain DAGs of Data Pipeline
in a more efficient way.

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

```yml
id: <your_dag_id>
type: dag
desc: <your_dag_description>
docs: docs.md
owners: [whoami@email.com]
labels:
  team: <team_name>
  system: <system_name>
  priority: <priority_level>
tags:
  - <tag1>
  - <tag2>
schedule: "0 * * * *"
start_date: "2023-01-01T00:00:00Z"
end_date: "2023-12-31T23:59:59Z"
catchup: true
max_active_runs: 1
max_active_tasks: 5
tasks:
  - id: <task-id>
    type: <task-type>
  - id: <task-id>
    type: <task-type>
    upstream: ["<task-id>"]
    trigger_rule: all_success
```
