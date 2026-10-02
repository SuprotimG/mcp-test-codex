from datetime import UTC, datetime
from pathlib import Path

from software_factory.adapters.podman import ContainerRunRequest, PodmanAdapter
from software_factory.adapters.state_store import LocalStateStore
from software_factory.domain.enums import AgentRole, AgentStatus, IssueStatus
from software_factory.domain.models import AgentRecord, IssueRecord, PlanRecord


class WorkerManager:
    def __init__(self, podman: PodmanAdapter, state_store: LocalStateStore) -> None:
        self.podman = podman
        self.state_store = state_store

    def assign_issue(self, issue: IssueRecord, plan: PlanRecord, agent_id: str, workspace_path: Path, branch_name: str) -> AgentRecord:
        logs_path = Path("var/artifacts/logs") / f"{agent_id}.log"
        agent = AgentRecord(
            agent_id=agent_id,
            role=AgentRole.DEVELOPER,
            status=AgentStatus.STARTING,
            issue_number=issue.number,
            plan_id=plan.plan_id,
            workspace_path=str(workspace_path),
            logs_path=str(logs_path),
            started_at=datetime.now(UTC),
        )
        issue.status = IssueStatus.ASSIGNED
        issue.assigned_agent_id = agent.agent_id
        issue.plan_id = plan.plan_id
        issue.branch_name = branch_name
        issue.updated_at = datetime.now(UTC)

        self.state_store.upsert_plan(plan)
        self.state_store.upsert_agent(agent)
        self.state_store.upsert_issue(issue)
        self.state_store.create_event(
            category="developer",
            message=f"Assigned issue #{issue.number} to developer agent {agent_id}",
            entity_type="issue",
            entity_id=str(issue.number),
            details={"agent_id": agent_id, "branch_name": branch_name},
        )

        container_name = self.podman.start_agent_container(
            ContainerRunRequest(
                agent_id=agent_id,
                role=AgentRole.DEVELOPER,
                issue_number=issue.number,
                plan_id=plan.plan_id,
                workspace_path=str(workspace_path),
                branch_name=branch_name,
            )
        )
        agent.container_name = container_name
        self.state_store.upsert_agent(agent)
        return agent

