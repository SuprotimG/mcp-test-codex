import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import BaseModel

from software_factory.domain.enums import AgentRole, AgentStatus, IssueStatus
from software_factory.domain.models import AgentRecord, DashboardSnapshot, EventRecord, IssueRecord, MergeRecord, PlanRecord, PullRequestRecord

ModelT = TypeVar("ModelT", bound=BaseModel)


SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    number INTEGER PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    plan_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pull_requests (
    number INTEGER PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS merges (
    pull_request_number INTEGER PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL
);
"""


class LocalStateStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def upsert_issue(self, issue: IssueRecord) -> None:
        self._upsert("issues", issue.number, issue)

    def upsert_plan(self, plan: PlanRecord) -> None:
        self._upsert("plans", plan.plan_id, plan)

    def upsert_agent(self, agent: AgentRecord) -> None:
        self._upsert("agents", agent.agent_id, agent)

    def upsert_pull_request(self, pull_request: PullRequestRecord) -> None:
        self._upsert("pull_requests", pull_request.number, pull_request)

    def upsert_merge(self, merge: MergeRecord) -> None:
        self._upsert("merges", merge.pull_request_number, merge)

    def append_event(self, event: EventRecord) -> EventRecord:
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO events(payload) VALUES(?)",
                (event.model_dump_json(),),
            )
        return event.model_copy(update={"event_id": cursor.lastrowid})

    def create_event(
        self,
        category: str,
        message: str,
        entity_type: str,
        entity_id: str,
        details: dict | None = None,
    ) -> EventRecord:
        event = EventRecord(
            category=category,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
        return self.append_event(event)

    def get_issue(self, issue_number: int) -> IssueRecord | None:
        return self._get("issues", issue_number, IssueRecord)

    def get_plan(self, plan_id: str) -> PlanRecord | None:
        return self._get("plans", plan_id, PlanRecord)

    def get_agent(self, agent_id: str) -> AgentRecord | None:
        return self._get("agents", agent_id, AgentRecord)

    def get_pull_request(self, pull_request_number: int) -> PullRequestRecord | None:
        return self._get("pull_requests", pull_request_number, PullRequestRecord)

    def get_merge(self, pull_request_number: int) -> MergeRecord | None:
        return self._get("merges", pull_request_number, MergeRecord)

    def find_pull_request_by_issue(self, issue_number: int) -> PullRequestRecord | None:
        for pull_request in self.list_pull_requests():
            if pull_request.issue_number == issue_number:
                return pull_request
        return None

    def list_issues(self) -> list[IssueRecord]:
        return self._list("issues", IssueRecord)

    def list_plans(self) -> list[PlanRecord]:
        return self._list("plans", PlanRecord)

    def list_agents(self) -> list[AgentRecord]:
        return self._list("agents", AgentRecord)

    def list_pull_requests(self) -> list[PullRequestRecord]:
        return self._list("pull_requests", PullRequestRecord)

    def list_merges(self) -> list[MergeRecord]:
        return self._list("merges", MergeRecord)

    def list_events(self, limit: int = 25) -> list[EventRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT event_id, payload FROM events ORDER BY event_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        events: list[EventRecord] = []
        for row in rows:
            event = EventRecord.model_validate_json(row["payload"])
            events.append(event.model_copy(update={"event_id": row["event_id"]}))
        return events

    def count_active_agents(self, role: AgentRole | None = None) -> int:
        active_statuses = {AgentStatus.STARTING, AgentStatus.RUNNING}
        return sum(
            1
            for agent in self.list_agents()
            if agent.status in active_statuses and (role is None or agent.role == role)
        )

    def has_active_agent(
        self,
        role: AgentRole,
        issue_number: int | None = None,
        pull_request_number: int | None = None,
    ) -> bool:
        active_statuses = {AgentStatus.STARTING, AgentStatus.RUNNING}
        for agent in self.list_agents():
            if agent.role != role or agent.status not in active_statuses:
                continue
            if issue_number is not None and agent.issue_number != issue_number:
                continue
            if pull_request_number is not None and agent.pull_request_number != pull_request_number:
                continue
            return True
        return False

    def get_dashboard_snapshot(self) -> DashboardSnapshot:
        return DashboardSnapshot(
            agents=self.list_agents(),
            issues=self.list_issues(),
            pull_requests=self.list_pull_requests(),
            merges=self.list_merges(),
            events=self.list_events(),
        )

    def reserve_next_issue(self) -> IssueRecord | None:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT payload FROM issues ORDER BY number ASC").fetchall()
            for row in rows:
                issue = IssueRecord.model_validate_json(row["payload"])
                if issue.status == IssueStatus.QUEUED:
                    issue.status = IssueStatus.PLANNED
                    issue.updated_at = datetime.now(UTC)
                    connection.execute(
                        "INSERT OR REPLACE INTO issues(number, payload) VALUES(?, ?)",
                        (issue.number, issue.model_dump_json()),
                    )
                    return issue
        return None

    def _get(self, table_name: str, primary_key: int | str, model_class: type[ModelT]) -> ModelT | None:
        column_name = {
            "issues": "number",
            "plans": "plan_id",
            "agents": "agent_id",
            "pull_requests": "number",
            "merges": "pull_request_number",
        }[table_name]
        with self.connection() as connection:
            row = connection.execute(
                f"SELECT payload FROM {table_name} WHERE {column_name} = ?",
                (primary_key,),
            ).fetchone()
        if row is None:
            return None
        return model_class.model_validate_json(row["payload"])

    def _upsert(self, table_name: str, primary_key: int | str, model: BaseModel) -> None:
        with self.connection() as connection:
            connection.execute(
                f"INSERT OR REPLACE INTO {table_name} VALUES(?, ?)",
                (primary_key, model.model_dump_json()),
            )

    def _list(self, table_name: str, model_class: type[ModelT]) -> list[ModelT]:
        with self.connection() as connection:
            rows = connection.execute(f"SELECT payload FROM {table_name} ORDER BY rowid ASC").fetchall()
        return [model_class.model_validate_json(row["payload"]) for row in rows]

