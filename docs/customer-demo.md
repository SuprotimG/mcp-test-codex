# Customer Demo Guide

## Goal

Use this repository to demonstrate an AFK software factory:

- GitHub issues become the work queue
- one issue is reserved per worker
- a planner agent creates the implementation contract
- developer agents work in isolated Podman containers
- reviewer and merger agents handle the PR pipeline
- the dashboard shows the factory state live

## Truthful positioning

This repository is the orchestration layer.

It manages:

- queueing
- persistence
- dashboarding
- Podman isolation
- planner, developer, reviewer, and merger lifecycles

The actual coding brain is provided through the role command profiles.

If you want to demonstrate Matt Pocock's Sandcastle specifically, plug Sandcastle into those command profiles.

## Suggested Sandcastle setup

1. Bootstrap the repository so `main` exists on GitHub.
2. Keep the included `.sandcastle/` files and `scripts/sandcastle/` wrappers in the repo.
3. Point these variables at those wrappers:

- `SOFTWARE_FACTORY_PLANNER_COMMAND`
- `SOFTWARE_FACTORY_DEVELOPER_COMMAND`
- `SOFTWARE_FACTORY_REVIEWER_COMMAND`
- `SOFTWARE_FACTORY_MERGER_COMMAND`

For a fast demo, start with the developer role first, then layer in reviewer and merger automation after the pipeline is stable.

If the GitHub repository is empty, start with:

```powershell
python -m software_factory.cli bootstrap-repository --push
```

That creates the first commit and pushes the default branch so the AFK worker factory can create feature branches and pull requests afterward.

## Recommended demo settings

```powershell
$env:SOFTWARE_FACTORY_GITHUB_TOKEN = '<token>'
$env:SOFTWARE_FACTORY_WORKER_IMAGE = 'localhost/software-factory-worker:latest'
$env:SOFTWARE_FACTORY_DRY_RUN = 'false'
$env:SOFTWARE_FACTORY_AUTO_APPROVE_PULL_REQUESTS = 'true'
$env:SOFTWARE_FACTORY_AUTO_MERGE_PULL_REQUESTS = 'true'
```

## Demo script

1. Open the dashboard.
2. Show open issues entering the local queue.
3. Start the scheduler.
4. Show a planner container generating the implementation plan.
5. Show a developer container claiming one issue and one isolated workspace clone.
6. Show PR state arriving in the dashboard.
7. Show reviewer and merger steps completing without manual clicks.

## Good customer language

Suggested phrasing:

- "GitHub Issues are the backlog and queue source."
- "Each issue is assigned to one isolated worker runtime."
- "The planner creates a contract before implementation starts."
- "The execution layer can run Sandcastle-powered agent commands inside Podman containers."
- "The control plane keeps durable state locally so the factory can recover after restarts."
