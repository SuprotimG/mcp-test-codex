from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from software_factory.domain.enums import AgentRole, AgentStatus, IssueStatus, MergeStatus, PullRequestStatus


def now_utc() -> datetime:
    return datetime.now(UTC)


class IssueRecord(BaseModel):
    number: int
    title: str
    body: str = ""
    labels: list[str] = Field(default_factory=list)
    status: IssueStatus = Field(default=IssueStatus.QUEUED)
    assigned_agent_id: str | None = None
    plan_id: str | None = None
    branch_name: str | None = None
    pull_request_number: int | None = None
    html_url: str | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class PlanRecord(BaseModel):
    plan_id: str
    issue_number: int
    summary: str
    steps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    artifact_path: str | None = None
    created_at: datetime = Field(default_factory=now_utc)


class AgentRecord(BaseModel):
    agent_id: str
    role: AgentRole
    status: AgentStatus = Field(default=AgentStatus.IDLE)
    issue_number: int | None = None
    pull_request_number: int | None = None
    plan_id: str | None = None
    container_name: str | None = None
    workspace_path: str | None = None
    logs_path: str | None = None
    exit_code: int | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PullRequestRecord(BaseModel):
    number: int
    issue_number: int | None = None
    title: str
    body: str = ""
    branch_name: str
    base_branch: str = ""
    status: PullRequestStatus = Field(default=PullRequestStatus.OPEN)
    html_url: str | None = None
    reviewer_agent_id: str | None = None
    review_summary: str | None = None
    merge_commit_sha: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    merged_at: datetime | None = None


class MergeRecord(BaseModel):
    pull_request_number: int
    issue_number: int | None = None
    status: MergeStatus = Field(default=MergeStatus.NOT_READY)
    attempted_at: datetime | None = None
    merged_at: datetime | None = None
    merge_commit_sha: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EventRecord(BaseModel):
    event_id: int | None = None
    category: str
    message: str
    entity_type: str
    entity_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class DashboardSnapshot(BaseModel):
    agents: list[AgentRecord] = Field(default_factory=list)
    issues: list[IssueRecord] = Field(default_factory=list)
    pull_requests: list[PullRequestRecord] = Field(default_factory=list)
    merges: list[MergeRecord] = Field(default_factory=list)
    events: list[EventRecord] = Field(default_factory=list)

