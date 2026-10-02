from software_factory.adapters.podman import ContainerRunRequest, PodmanAdapter
from software_factory.adapters.state_store import LocalStateStore
from software_factory.domain.enums import AgentRole, AgentStatus
from software_factory.domain.models import AgentRecord, PullRequestRecord


class ReviewManager:
    def __init__(self, state_store: LocalStateStore, podman: PodmanAdapter) -> None:
        self.state_store = state_store
        self.podman = podman

    def dispatch_review(self, pull_request: PullRequestRecord, agent_id: str) -> AgentRecord:
        agent = AgentRecord(
            agent_id=agent_id,
            role=AgentRole.REVIEWER,
            status=AgentStatus.STARTING,
            issue_number=pull_request.issue_number,
            pull_request_number=pull_request.number,
        )
        pull_request.reviewer_agent_id = agent_id
        self.state_store.upsert_pull_request(pull_request)
        self.state_store.upsert_agent(agent)
        self.state_store.create_event(
            category="review",
            message=f"Dispatching reviewer for PR #{pull_request.number}",
            entity_type="pull_request",
            entity_id=str(pull_request.number),
            details={"agent_id": agent_id},
        )
        result = self.podman.run_agent_once(
            ContainerRunRequest(
                agent_id=agent_id,
                role=AgentRole.REVIEWER,
                issue_number=pull_request.issue_number,
                pull_request_number=pull_request.number,
            )
        )
        agent = self.state_store.get_agent(agent_id) or agent
        agent.exit_code = result.exit_code
        if result.exit_code != 0 and agent.status != AgentStatus.FAILED:
            agent.status = AgentStatus.FAILED
            agent.last_error = result.stderr.strip() or result.stdout.strip() or "Reviewer container failed"
            self.state_store.upsert_agent(agent)
        return agent

