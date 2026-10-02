from enum import StrEnum


class IssueStatus(StrEnum):
    QUEUED = "queued"
    PLANNED = "planned"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    MERGED = "merged"
    BLOCKED = "blocked"
    FAILED = "failed"


class AgentRole(StrEnum):
    PLANNER = "planner"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    MERGER = "merger"


class AgentStatus(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class PullRequestStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    MERGED = "merged"
    CLOSED = "closed"


class MergeStatus(StrEnum):
    NOT_READY = "not_ready"
    READY = "ready"
    MERGING = "merging"
    MERGED = "merged"
    FAILED = "failed"

