# Implementation Plan

## Phase 0 — foundation

Deliverables:

- repository scaffold
- domain models and enums
- config and local state conventions
- dashboard skeleton
- Podman container definitions

Exit criteria:

- repo builds as a Python package
- app starts with placeholder endpoints
- local state directory structure exists

## Phase 1 — local orchestration core

Deliverables:

- SQLite-backed state store
- issue queue manager
- scheduler loop
- planner and worker manager interfaces
- audit event persistence

Exit criteria:

- queue transitions are durable
- only one worker can reserve an issue at a time
- scheduler can recover after restart

## Phase 2 — GitHub synchronization

Deliverables:

- issue polling adapter
- PR metadata synchronization
- repository settings abstraction

Exit criteria:

- open issues sync into the queue
- queue updates survive resyncs
- PR status is visible in the dashboard

## Phase 3 — isolated execution

Deliverables:

- Podman container runner
- planner container contract
- developer container contract
- workspace provisioning and cleanup

Exit criteria:

- multiple workers run concurrently in isolated containers
- each worker receives one issue and one plan
- worker state is recoverable locally

## Phase 4 — review and merge pipeline

Deliverables:

- reviewer agent contract
- merge policy checks
- merge queue
- audit trail for approvals and merges

Exit criteria:

- completed PRs enter review automatically
- approved PRs can be merged by policy
- merge state is visible in the dashboard

## Phase 5 — operational hardening

Deliverables:

- health checks and alerts
- retry and backoff strategy
- timeout handling
- manual override controls

Exit criteria:

- failed runs are diagnosable
- stale workers can be reaped safely
- operators can inspect and control the queue

