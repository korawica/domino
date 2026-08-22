# DAG Design

A DAG YAML template design.

```yml
id: <dag-id>
type: dag
name: <DAG Display Name>
desc: <Description of the DAG>
tags:
  - batch
  - hourly
labels:
  priority: high
  team: data
  domain: inventory
  system: pos

schedule: "0 * * * *"
start_date: "2023-01-01T00:00:00Z"
end_date: "2023-12-31T23:59:59Z"
catchup: true

max_active_runs: 1
max_active_tasks: 5
max_consecutive_failed_dag_runs: null
dagrun_timeout_sec: null

tasks:
  - id: task-id
    type: task

  - id: task-id
    type: task
    upstream: ["task-id"]
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
  priority: high
  team: data
  domain: inventory
  system: pos
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
