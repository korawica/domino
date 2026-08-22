# DAG Design

A DAG YAML template design.

```yml
id: <dag-id>
type: dag
name: <DAG Display Name>
desc: <Description of the DAG>
labels:
  team: admin
  priority: p5
  domain: inventory
  system: internal
tags:
  - batch
  - hourly

schedule: "0 * * * *"
start_date: "2023-01-01T00:00:00Z"
end_date: "2023-12-31T23:59:59Z"
catchup: true

max_active_runs: 1
max_active_tasks: 5
max_consecutive_failed_dag_runs: null
dagrun_timeout_sec: null

tasks:
  - id: <task-id>
    type: <task-type>

  - id: <task-id>
    type: <task-type>
    upstream: ["<task-id>"]
    trigger_rule: all_success
```

## Metadata

```yml
id: <dag-id>
type: dag
name: <DAG Display Name>
desc: <Description of the DAG>
tags:
  - batch
  - hourly
labels:
  priority: p5
  team: admin
  domain: inventory
  system: internal
```

## Schedule

```yml
schedule: "0 * * * *"
start_date: "2023-01-01T00:00:00Z"
end_date: "2023-12-31T23:59:59Z"
catchup: true
```

## Execution Constraints

```yml
max_active_runs: 1
max_active_tasks: 5
max_consecutive_failed_dag_runs: null
dagrun_timeout_sec: null
```

## Tasks

```yml
tasks:
  - id: task-id
    type: task
    using: empty
```
