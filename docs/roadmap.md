# Roadmap

## Milestone 1 — control plane scaffold

Target outcome:

- a runnable orchestrator skeleton with local persistence and a dashboard shell

Includes:

- package structure
- local config
- state models
- scheduler and manager stubs
- Podman runtime abstraction

## Milestone 2 — issue intake and queueing

Target outcome:

- GitHub issues appear in a durable local queue with clear lifecycle states

Includes:

- issue sync
- priority rules
- assignment locks
- queue inspection APIs

## Milestone 3 — parallel worker execution

Target outcome:

- multiple isolated developer workers can run in parallel without duplicate issue ownership

Includes:

- planner handoff
- per-worker workspace provisioning
- container lifecycle tracking
- heartbeats and retries

## Milestone 4 — review and merge automation

Target outcome:

- completed pull requests flow through review to merge with auditability

Includes:

- reviewer pipeline
- approval state tracking
- merge queue
- merge policy enforcement

## Milestone 5 — operator experience

Target outcome:

- the dashboard becomes the control center for the software factory

Includes:

- rich filters and search
- action buttons for retry, pause, resume, and reassign
- event timeline and artifacts viewer

