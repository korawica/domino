# Task

A task YAML template design.

## Common Fields

```yml
tasks:
  - id: <task-id>
    name: <task display name>
    type: <task-type>

    upstream: [<upstream-task-id>]
    trigger_rule: <trigger-rule>

    uses: <task-implemented-tool>
    inputs:
      <input-1-name>: <input-1-value>
      <input-2-name>: <input-2-value>
      <input-3-name>: <input-3-value>

    inlets:
        - <inlet-name>
    outlets:
        - <outlet-name>
```

## Task Types

### Base Task

```yml
tasks:
  - id: <task-id>
    type: <task-type>

    timeout: 3600
    retries: 3
    retry_delay: 60
    retry_exponential_backoff: true
```

### Sensor

```yml
tasks:
  - id: <task-id>
    type: <sensor-type>

    mode: poke
    poke_interval: 60
```

### Group

```yml
tasks:
  - id: <task-id>
    name: <task display name>
    type: group
    tasks:
      - id: <task-id>
        type: <task-type>
```

### Branch

```yml
tasks:
  - id: <task-id>
    type: <branch-type>
```

### Short Circuit

```yml
tasks:
  - id: <task-id>
    type: <short-circuit-type>
```
