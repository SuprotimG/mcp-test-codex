from datetime import UTC, datetime

from software_factory.adapters.podman import ContainerRunRequest, PodmanAdapter
from software_factory.adapters.state_store import LocalStateStore
from software_factory.domain.enums import AgentRole, AgentStatus, MergeStatus
from software_factory.domain.models import AgentRecord, MergeRecord, PullRequestRecord


class MergeManager:
    def __init__(self, state_store: LocalStateStore, podman: PodmanAdapter) -> None:
        self.state_store = state_store
        self.podman = podman

    def dispatch_merge(self, pull_request: PullRequestRecord, agent_id: str) -> AgentRecord:
        merge_record = self.state_store.get_merge(pull_request.number) or MergeRecord(
            pull_request_number=pull_request.number,
            issue_number=pull_request.issue_number,
        )
        merge_record.status = MergeStatus.MERGING
        merge_record.attempted_at = datetime.now(UTC)
        self.state_store.upsert_merge(merge_record)

        agent = AgentRecord(
            agent_id=agent_id,
            role=AgentRole.MERGER,
            status=AgentStatus.STARTING,
            issue_number=pull_request.issue_number,
            pull_request_number=pull_request.number,
        )
        self.state_store.upsert_agent(agent)
        self.state_store.create_event(
            category="merge",
            message=f"Dispatching merger for PR #{pull_request.number}",
            entity_type="pull_request",
            entity_id=str(pull_request.number),
            details={"agent_id": agent_id},
        )

        result = self.podman.run_agent_once(
            ContainerRunRequest(
                agent_id=agent_id,
                role=AgentRole.MERGER,
                issue_number=pull_request.issue_number,
                pull_request_number=pull_request.number,
            )
        )
        agent = self.state_store.get_agent(agent_id) or agent
        agent.exit_code = result.exit_code
        if result.exit_code != 0 and agent.status != AgentStatus.FAILED:
            agent.status = AgentStatus.FAILED
            agent.last_error = result.stderr.strip() or result.stdout.strip() or "Merger container failed"
            self.state_store.upsert_agent(agent)
            merge_record.status = MergeStatus.FAILED
            self.state_store.upsert_merge(merge_record)
        return agent

