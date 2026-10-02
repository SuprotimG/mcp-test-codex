from datetime import UTC, datetime

from software_factory.adapters.git import GitWorkspaceAdapter, RepositoryNotReadyError
from software_factory.adapters.github import GitHubAdapter
from software_factory.adapters.podman import PodmanAdapter
from software_factory.adapters.state_store import LocalStateStore
from software_factory.domain.enums import AgentRole, AgentStatus, IssueStatus, MergeStatus, PullRequestStatus
from software_factory.domain.models import MergeRecord, PullRequestRecord
from software_factory.services.merge_manager import MergeManager
from software_factory.services.planner import PlannerService
from software_factory.services.queue_manager import QueueManager
from software_factory.services.review_manager import ReviewManager
from software_factory.services.worker_manager import WorkerManager
from software_factory.settings import Settings


class Coordinator:
    def __init__(self, settings: Settings, state_store: LocalStateStore) -> None:
        self.settings = settings
        self.state_store = state_store
        self.github = GitHubAdapter(settings)
        self.podman = PodmanAdapter(settings)
        self.git = GitWorkspaceAdapter(settings.repository_path, settings.git_identity, settings.git_workflow)
        self.queue = QueueManager(state_store)
        self.planner = PlannerService(state_store, self.podman, settings.runtime_paths.artifacts)
        self.workers = WorkerManager(self.podman, state_store)
        self.review = ReviewManager(state_store, self.podman)
        self.merge = MergeManager(state_store, self.podman)

    def sync(self) -> None:
        snapshot = self.github.sync_repository()
        self.queue.ingest_issues(snapshot.issues)
        for pull_request in snapshot.pull_requests:
            self.state_store.upsert_pull_request(pull_request)
            self._reconcile_pull_request(pull_request)

    def reconcile_agents(self) -> None:
        for agent in self.state_store.list_agents():
            if agent.status not in {AgentStatus.STARTING, AgentStatus.RUNNING}:
                continue
            if not agent.container_name:
                continue
            details = self.podman.inspect_container(agent.container_name)
            if details is None:
                continue
            state = details.get("State", {})
            if state.get("Running"):
                agent.status = AgentStatus.RUNNING
                agent.heartbeat_at = datetime.now(UTC)
                self.state_store.upsert_agent(agent)
                continue

            agent.exit_code = state.get("ExitCode")
            agent.finished_at = datetime.now(UTC)
            agent.heartbeat_at = datetime.now(UTC)
            agent.status = AgentStatus.COMPLETED if agent.exit_code == 0 else AgentStatus.FAILED
            if agent.status == AgentStatus.FAILED:
                agent.last_error = state.get("Error") or f"Container {agent.container_name} failed"
            self.state_store.upsert_agent(agent)
            self._reconcile_completed_agent(agent)

    def run_once(self) -> None:
        self.reconcile_agents()
        self.sync()
        self.dispatch_reviews()
        self.dispatch_merges()
        self.dispatch_developers()

    def dispatch_reviews(self) -> None:
        if not self.settings.commands.reviewer_command and not self.settings.merge_policy.auto_approve_pull_requests:
            return
        for pull_request in self.state_store.list_pull_requests():
            if pull_request.status not in {PullRequestStatus.OPEN, PullRequestStatus.REVIEW_PENDING}:
                continue
            if pull_request.reviewer_agent_id is not None:
                continue
            if self.state_store.has_active_agent(AgentRole.REVIEWER, pull_request_number=pull_request.number):
                continue
            agent_id = f"reviewer-{pull_request.number}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
            self.review.dispatch_review(pull_request, agent_id)

    def dispatch_merges(self) -> None:
        if not self.settings.commands.merger_command and not self.settings.merge_policy.auto_merge_pull_requests:
            return
        for pull_request in self.state_store.list_pull_requests():
            if pull_request.status != PullRequestStatus.APPROVED:
                continue
            merge_record = self.state_store.get_merge(pull_request.number) or MergeRecord(
                pull_request_number=pull_request.number,
                issue_number=pull_request.issue_number,
            )
            if merge_record.status in {MergeStatus.MERGING, MergeStatus.MERGED}:
                continue
            if self.state_store.has_active_agent(AgentRole.MERGER, pull_request_number=pull_request.number):
                continue
            agent_id = f"merger-{pull_request.number}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
            self.merge.dispatch_merge(pull_request, agent_id)

    def dispatch_developers(self) -> None:
        while self.state_store.count_active_agents(AgentRole.DEVELOPER) < self.settings.max_parallel_workers:
            issue = self.queue.reserve_next_issue()
            if issue is None:
                return
            suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            developer_agent_id = f"developer-{issue.number}-{suffix}"
            planner_agent_id = f"planner-{issue.number}-{suffix}"
            try:
                workspace = self.git.prepare_issue_workspace(issue.number, issue.title, self.settings.runtime_paths.workspaces, developer_agent_id)
                issue.branch_name = workspace.branch_name
                self.state_store.upsert_issue(issue)
                plan = self.planner.dispatch_plan(issue, workspace.path, workspace.branch_name, planner_agent_id)
                self.workers.assign_issue(
                    issue=issue,
                    plan=plan,
                    agent_id=developer_agent_id,
                    workspace_path=workspace.path,
                    branch_name=workspace.branch_name,
                )
            except RepositoryNotReadyError as error:
                issue.status = IssueStatus.BLOCKED
                issue.last_error = str(error)
                issue.updated_at = datetime.now(UTC)
                self.state_store.upsert_issue(issue)
                self.state_store.create_event(
                    category="scheduler",
                    message=f"Repository bootstrap required before issue #{issue.number} can run",
                    entity_type="issue",
                    entity_id=str(issue.number),
                    details={"error": str(error)},
                )
                return
            except Exception as error:
                issue.status = IssueStatus.FAILED
                issue.last_error = str(error)
                issue.updated_at = datetime.now(UTC)
                self.state_store.upsert_issue(issue)
                self.state_store.create_event(
                    category="scheduler",
                    message=f"Failed to dispatch issue #{issue.number}",
                    entity_type="issue",
                    entity_id=str(issue.number),
                    details={"error": str(error)},
                )

    def _reconcile_pull_request(self, pull_request: PullRequestRecord) -> None:
        merge_record = self.state_store.get_merge(pull_request.number) or MergeRecord(
            pull_request_number=pull_request.number,
            issue_number=pull_request.issue_number,
        )
        if pull_request.status == PullRequestStatus.APPROVED:
            merge_record.status = MergeStatus.READY
        elif pull_request.status == PullRequestStatus.MERGED:
            merge_record.status = MergeStatus.MERGED
            merge_record.merged_at = pull_request.merged_at or datetime.now(UTC)
            merge_record.merge_commit_sha = pull_request.merge_commit_sha
        else:
            merge_record.status = MergeStatus.NOT_READY
        self.state_store.upsert_merge(merge_record)

        if pull_request.issue_number is None:
            return
        issue = self.state_store.get_issue(pull_request.issue_number)
        if issue is None:
            return
        issue.pull_request_number = pull_request.number
        issue.updated_at = datetime.now(UTC)
        if pull_request.status == PullRequestStatus.APPROVED:
            issue.status = IssueStatus.APPROVED
        elif pull_request.status == PullRequestStatus.MERGED:
            issue.status = IssueStatus.MERGED
        else:
            issue.status = IssueStatus.REVIEW_PENDING
        self.state_store.upsert_issue(issue)

    def _reconcile_completed_agent(self, agent) -> None:
        if agent.issue_number is None:
            return
        issue = self.state_store.get_issue(agent.issue_number)
        if issue is None:
            return
        if agent.role == AgentRole.DEVELOPER and agent.status == AgentStatus.FAILED:
            issue.status = IssueStatus.FAILED
            issue.last_error = agent.last_error
            issue.updated_at = datetime.now(UTC)
            self.state_store.upsert_issue(issue)
