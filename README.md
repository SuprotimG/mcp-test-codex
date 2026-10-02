# Autonomous Software Factory MVP

This repository contains an MVP swarm orchestration framework for autonomous development.

The framework now focuses on the orchestration layer required to run an AFK software-factory demo:

- read GitHub issues into a durable local queue
- reserve one issue per worker
- create a planner artifact before implementation starts
- run isolated planner, developer, reviewer, and merger agents in Podman containers
- persist issue, PR, merge, agent, and event state locally in SQLite
- expose a FastAPI dashboard for operators and customer demos

It still avoids implementing repository-specific business features. The developer, reviewer, and merger roles are driven by command profiles so you can plug in your preferred coding agent runtime.

## What works now

- live GitHub issue and PR synchronization
- durable local queue with assignment state preserved across syncs
- per-issue isolated git clones under `var/workspaces/`
- synchronous planner containers and parallel detached developer containers
- reviewer and merger agent dispatch hooks
- local artifacts for plans, logs, reviews, and merge notes
- dashboard visibility for agents, issues, PRs, merges, and recent events

## Architecture highlights

- `src/software_factory/adapters/github.py` talks to the GitHub REST API
- `src/software_factory/adapters/git.py` prepares isolated per-issue workspaces
- `src/software_factory/adapters/podman.py` launches role-specific Podman containers
- `src/software_factory/adapters/state_store.py` persists the durable factory state in SQLite
- `src/software_factory/services/coordinator.py` drives sync, dispatch, review, merge, and reconciliation
- `src/software_factory/services/agent_runtime.py` is the shared in-container runtime for planner, developer, reviewer, and merger roles

## Command profiles

The orchestration control plane is agent-agnostic.

Set these environment variables to plug in your actual implementation runtime:

- `SOFTWARE_FACTORY_PLANNER_COMMAND`
- `SOFTWARE_FACTORY_DEVELOPER_COMMAND`
- `SOFTWARE_FACTORY_REVIEWER_COMMAND`
- `SOFTWARE_FACTORY_MERGER_COMMAND`

Each command runs inside the relevant container with the factory environment already injected.

Useful environment variables available to those commands include:

- `SOFTWARE_FACTORY_ROLE`
- `SOFTWARE_FACTORY_AGENT_ID`
- `SOFTWARE_FACTORY_ISSUE_NUMBER`
- `SOFTWARE_FACTORY_PULL_REQUEST_NUMBER`
- `SOFTWARE_FACTORY_PLAN_ID`
- `SOFTWARE_FACTORY_BRANCH_NAME`
- `SOFTWARE_FACTORY_REPOSITORY_PATH`

The repo now includes Sandcastle role wrappers under `scripts/sandcastle/` and prompt templates under `.sandcastle/`.

Recommended defaults:

```powershell
$env:SOFTWARE_FACTORY_PLANNER_COMMAND = 'bash ./scripts/sandcastle/run-role.sh planner'
$env:SOFTWARE_FACTORY_DEVELOPER_COMMAND = 'bash ./scripts/sandcastle/run-role.sh developer'
$env:SOFTWARE_FACTORY_REVIEWER_COMMAND = 'bash ./scripts/sandcastle/run-role.sh reviewer'
$env:SOFTWARE_FACTORY_MERGER_COMMAND = 'bash ./scripts/sandcastle/run-role.sh merger'
$env:SOFTWARE_FACTORY_SANDCASTLE_AGENT = 'codex'
$env:SOFTWARE_FACTORY_SANDCASTLE_SANDBOX = 'no-sandbox'
```

## Podman workflow

Build the worker image first:

```powershell
podman build -f containers/worker.Containerfile -t localhost/software-factory-worker:latest .
```

Install the Python package locally:

```powershell
python -m pip install --user -e .
```

If you want to use the local `package.json` workflow instead of transient `npx` package downloads, run:

```powershell
npm install
```

## Empty repository bootstrap

Your GitHub repo currently being empty is important: PR automation needs a real default branch and at least one commit before the factory can create feature branches and open pull requests. GitHub's own workflow docs describe creating the first commit when starting from an empty repository, and pull requests operate by comparing branches against a base branch. citeturn0search14turn0search15

This repo now includes a safe bootstrap command that creates the first local commit without pushing anything automatically:

```powershell
python -m software_factory.cli bootstrap-repository
```

When you are ready to publish the initial branch to GitHub, run:

```powershell
python -m software_factory.cli bootstrap-repository --push
```

After that, the developer runtime can commit to per-issue branches, push them, and create PRs automatically.

Run a sync-only smoke test without dispatching developers:

```powershell
$env:SOFTWARE_FACTORY_MAX_PARALLEL_WORKERS = '0'
python -m software_factory.cli run-once
```

Start the dashboard and scheduler:

```powershell
uvicorn software_factory.api.app:create_app --factory --reload
python -m software_factory.cli run-scheduler
```

## Demo configuration

Copy `.env.example` and fill in the relevant values.

Recommended demo switches:

- `SOFTWARE_FACTORY_GITHUB_TOKEN` for GitHub API writes
- `SOFTWARE_FACTORY_WORKER_IMAGE=localhost/software-factory-worker:latest`
- `SOFTWARE_FACTORY_PODMAN_NETWORK=bridge` so Sandcastle can reach its agent backend and transient npm packages if needed
- `SOFTWARE_FACTORY_AUTO_COMMIT_CHANGES=true` so the control plane creates commits after the developer agent finishes
- `SOFTWARE_FACTORY_AUTO_CREATE_PULL_REQUESTS=true` so the control plane opens PRs after pushing the issue branch
- `SOFTWARE_FACTORY_DRY_RUN=false` for real review and merge actions
- `SOFTWARE_FACTORY_AUTO_APPROVE_PULL_REQUESTS=true` if you want the reviewer agent to approve PRs automatically
- `SOFTWARE_FACTORY_AUTO_MERGE_PULL_REQUESTS=true` if you want the merger agent to merge approved PRs automatically

## Sandcastle demo path

If your goal is to show a customer a Matt Pocock-style Sandcastle AFK workflow, this repo gives you the orchestration shell around it.

The cleanest path is:

1. bootstrap the repo so GitHub has a real default branch
2. use the included Sandcastle wrapper scripts for planner, developer, reviewer, and merger behavior
3. point the `SOFTWARE_FACTORY_*_COMMAND` environment variables at those scripts
4. let this control plane handle queueing, persistence, Podman isolation, dashboarding, commit/push/PR automation, and merge orchestration

See `docs/customer-demo.md` for the customer-facing demo story.

## Important limitations

- Podman must be installed on the host running the scheduler
- the worker image must be built before developers can be dispatched
- an empty repository must be bootstrapped before issue branches and PRs can be created
- unattended review and merge writes require `SOFTWARE_FACTORY_GITHUB_TOKEN`
- this repo orchestrates the swarm; it does not yet contain repository-specific coding logic

## Reference docs

- `docs/architecture.md`
- `docs/folder-structure.md`
- `docs/implementation-plan.md`
- `docs/roadmap.md`
- `docs/customer-demo.md`
