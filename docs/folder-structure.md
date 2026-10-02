# Folder Structure

## Top level

```text
.
├── .sandcastle/
├── .env.example
├── compose.yaml
├── containers/
├── docs/
├── package.json
├── scripts/
├── src/
│   └── software_factory/
├── var/
│   ├── artifacts/
│   ├── state/
│   └── workspaces/
└── pyproject.toml
```

## Source tree

```text
src/software_factory/
├── api/
│   ├── app.py
│   └── routes/
├── adapters/
│   ├── git.py
│   ├── github.py
│   ├── podman.py
│   └── state_store.py
├── domain/
│   ├── enums.py
│   └── models.py
├── services/
│   ├── agent_runtime.py
│   ├── coordinator.py
│   ├── merge_manager.py
│   ├── planner.py
│   ├── queue_manager.py
│   ├── review_manager.py
│   ├── scheduler.py
│   └── worker_manager.py
├── templates/
├── static/
├── bootstrap.py
├── cli.py
├── config.py
└── settings.py
```

## Why this structure

- `domain/` isolates durable business concepts from infrastructure
- `services/` expresses orchestration behavior without transport concerns
- `adapters/` keeps external dependencies replaceable
- `api/` provides dashboard and machine-readable operational endpoints
- `containers/` captures Podman-specific runtime packaging
- `var/` holds local runtime state outside the source tree logic

## Future growth

This layout supports future extraction into separate deployable services without forcing that complexity in the MVP.
