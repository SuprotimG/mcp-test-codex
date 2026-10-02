from datetime import UTC, datetime

from software_factory.adapters.state_store import LocalStateStore
from software_factory.domain.models import IssueRecord


class QueueManager:
    def __init__(self, state_store: LocalStateStore) -> None:
        self.state_store = state_store

    def ingest_issues(self, issues: list[IssueRecord]) -> None:
        for issue in issues:
            existing = self.state_store.get_issue(issue.number)
            if existing is not None:
                issue.status = existing.status
                issue.assigned_agent_id = existing.assigned_agent_id
                issue.plan_id = existing.plan_id
                issue.branch_name = existing.branch_name
                issue.pull_request_number = existing.pull_request_number
                issue.last_error = existing.last_error
                issue.created_at = existing.created_at
                issue.updated_at = datetime.now(UTC)
            self.state_store.upsert_issue(issue)

    def reserve_next_issue(self) -> IssueRecord | None:
        return self.state_store.reserve_next_issue()

