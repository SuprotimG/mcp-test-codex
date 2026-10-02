from pathlib import Path

from software_factory.adapters.podman import ContainerRunRequest, PodmanAdapter
from software_factory.adapters.state_store import LocalStateStore
from software_factory.domain.enums import AgentRole, AgentStatus, IssueStatus
from software_factory.domain.models import AgentRecord, IssueRecord, PlanRecord


class PlannerService:
    def __init__(self, state_store: LocalStateStore, podman: PodmanAdapter, artifacts_root: Path) -> None:
        self.state_store = state_store
        self.podman = podman
        self.artifacts_root = artifacts_root

    def dispatch_plan(self, issue: IssueRecord, workspace_path: Path, branch_name: str, agent_id: str) -> PlanRecord:
        planner_agent = AgentRecord(
            agent_id=agent_id,
            role=AgentRole.PLANNER,
            status=AgentStatus.STARTING,
            issue_number=issue.number,
            workspace_path=str(workspace_path),
        )
        self.state_store.upsert_agent(planner_agent)
        self.state_store.create_event(
            category="planner",
            message=f"Dispatching planner for issue #{issue.number}",
            entity_type="issue",
            entity_id=str(issue.number),
            details={"agent_id": agent_id, "branch_name": branch_name},
        )
        result = self.podman.run_agent_once(
            ContainerRunRequest(
                agent_id=agent_id,
                role=AgentRole.PLANNER,
                issue_number=issue.number,
                workspace_path=str(workspace_path),
                branch_name=branch_name,
            )
        )
        if result.exit_code != 0:
            issue.status = IssueStatus.FAILED
            issue.last_error = result.stderr.strip() or result.stdout.strip() or "Planner container failed"
            self.state_store.upsert_issue(issue)
            failed_agent = self.state_store.get_agent(agent_id) or planner_agent
            failed_agent.status = AgentStatus.FAILED
            failed_agent.exit_code = result.exit_code
            failed_agent.last_error = issue.last_error
            self.state_store.upsert_agent(failed_agent)
            self.state_store.create_event(
                category="planner",
                message=f"Planner failed for issue #{issue.number}",
                entity_type="issue",
                entity_id=str(issue.number),
                details={"agent_id": agent_id, "stderr": result.stderr},
            )
            raise RuntimeError(issue.last_error)

        plan = self.state_store.get_plan(f"plan-{issue.number}") or self.create_default_plan(issue, branch_name)
        self.state_store.upsert_plan(plan)
        issue.plan_id = plan.plan_id
        self.state_store.upsert_issue(issue)
        return plan

    @staticmethod
    def create_default_plan(issue: IssueRecord, branch_name: str | None = None) -> PlanRecord:
        return PlanRecord(
            plan_id=f"plan-{issue.number}",
            issue_number=issue.number,
            summary=f"Implement issue #{issue.number}: {issue.title}",
            steps=[
                "Inspect the repository and issue context inside an isolated workspace clone",
                f"Implement the change on branch {branch_name or 'factory/issue-*'}",
                "Run repository checks and create a pull request linked to the issue",
                "Hand the result to automated review and merge stages",
            ],
            risks=[
                "Developer command must know how to change this repository safely",
                "GitHub credentials and push permissions are required for a fully unattended PR flow",
            ],
        )

    @staticmethod
    def render_markdown(plan: PlanRecord) -> str:
        lines = [f"# {plan.summary}", "", "## Steps", ""]
        lines.extend(f"- {step}" for step in plan.steps)
        lines.extend(["", "## Risks", ""])
        lines.extend(f"- {risk}" for risk in plan.risks)
        return "\n".join(lines)

