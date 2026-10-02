import os
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path

from software_factory.adapters.git import GitWorkspaceAdapter
from software_factory.adapters.github import GitHubAdapter
from software_factory.adapters.state_store import LocalStateStore
from software_factory.domain.enums import AgentRole, AgentStatus, IssueStatus, MergeStatus, PullRequestStatus
from software_factory.domain.models import AgentRecord, MergeRecord
from software_factory.services.planner import PlannerService
from software_factory.settings import Settings


class AgentRuntimeService:
    def __init__(self, settings: Settings, state_store: LocalStateStore) -> None:
        self.settings = settings
        self.state_store = state_store
        self.github = GitHubAdapter(settings)
        self.git = GitWorkspaceAdapter(settings.repository_path, settings.git_identity, settings.git_workflow)

    def run(
        self,
        role: AgentRole,
        agent_id: str,
        issue_number: int | None = None,
        pull_request_number: int | None = None,
        plan_id: str | None = None,
        workspace_path: str | None = None,
        branch_name: str | None = None,
    ) -> int:
        agent = self.state_store.get_agent(agent_id) or AgentRecord(
            agent_id=agent_id,
            role=role,
            issue_number=issue_number,
            pull_request_number=pull_request_number,
            plan_id=plan_id,
            workspace_path=workspace_path,
        )
        agent.status = AgentStatus.RUNNING
        agent.started_at = agent.started_at or datetime.now(UTC)
        agent.heartbeat_at = datetime.now(UTC)
        self.state_store.upsert_agent(agent)

        stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(agent_id, stop_event),
            daemon=True,
        )
        heartbeat_thread.start()

        try:
            if role == AgentRole.PLANNER:
                self._run_planner(issue_number=issue_number)
            elif role == AgentRole.DEVELOPER:
                self._run_developer(agent_id=agent_id, issue_number=issue_number, workspace_path=workspace_path, branch_name=branch_name)
            elif role == AgentRole.REVIEWER:
                self._run_reviewer(agent_id=agent_id, pull_request_number=pull_request_number)
            elif role == AgentRole.MERGER:
                self._run_merger(agent_id=agent_id, pull_request_number=pull_request_number)
            else:
                raise RuntimeError(f"Unsupported role: {role}")

            agent = self.state_store.get_agent(agent_id) or agent
            agent.status = AgentStatus.COMPLETED
            agent.finished_at = datetime.now(UTC)
            agent.heartbeat_at = datetime.now(UTC)
            self.state_store.upsert_agent(agent)
            return 0
        except Exception as error:
            agent = self.state_store.get_agent(agent_id) or agent
            agent.status = AgentStatus.FAILED
            agent.finished_at = datetime.now(UTC)
            agent.heartbeat_at = datetime.now(UTC)
            agent.last_error = str(error)
            self.state_store.upsert_agent(agent)
            return 1
        finally:
            stop_event.set()
            heartbeat_thread.join(timeout=1)

    def _run_planner(self, issue_number: int | None) -> None:
        if issue_number is None:
            raise RuntimeError("Planner requires an issue number")
        issue = self.state_store.get_issue(issue_number)
        if issue is None:
            raise RuntimeError(f"Unknown issue #{issue_number}")

        plan = PlannerService.create_default_plan(issue, issue.branch_name)
        artifact_path = self._write_artifact(
            category="plans",
            name=f"issue-{issue.number}.md",
            content=PlannerService.render_markdown(plan),
        )
        plan.artifact_path = str(artifact_path)
        issue.plan_id = plan.plan_id
        issue.updated_at = datetime.now(UTC)
        self.state_store.upsert_plan(plan)
        self.state_store.upsert_issue(issue)

        if self.settings.commands.planner_command:
            self._run_external_command(
                command=self.settings.commands.planner_command,
                cwd=Path(self.settings.repository_path),
                extra_env=self._build_agent_env(
                    issue_number=issue.number,
                    issue_title=issue.title,
                    issue_body=issue.body,
                    branch_name=issue.branch_name,
                    plan_id=plan.plan_id,
                    plan_artifact_path=str(artifact_path),
                ),
            )

        self.state_store.create_event(
            category="planner",
            message=f"Planner completed for issue #{issue.number}",
            entity_type="issue",
            entity_id=str(issue.number),
            details={"plan_id": plan.plan_id, "artifact_path": str(artifact_path)},
        )

    def _run_developer(self, agent_id: str, issue_number: int | None, workspace_path: str | None, branch_name: str | None) -> None:
        if issue_number is None:
            raise RuntimeError("Developer requires an issue number")
        issue = self.state_store.get_issue(issue_number)
        if issue is None:
            raise RuntimeError(f"Unknown issue #{issue_number}")
        if workspace_path is None:
            raise RuntimeError("Developer requires a workspace path")

        workspace = Path(workspace_path)
        issue.status = IssueStatus.IN_PROGRESS
        issue.branch_name = branch_name or issue.branch_name or self.git.get_current_branch(workspace)
        issue.updated_at = datetime.now(UTC)
        self.state_store.upsert_issue(issue)

        plan = self.state_store.get_plan(issue.plan_id) if issue.plan_id else None
        plan_artifact_path = plan.artifact_path if plan is not None else None
        if self.settings.commands.developer_command:
            self._run_external_command(
                command=self.settings.commands.developer_command,
                cwd=workspace,
                agent_id=agent_id,
                extra_env=self._build_agent_env(
                    issue_number=issue.number,
                    issue_title=issue.title,
                    issue_body=issue.body,
                    branch_name=issue.branch_name,
                    plan_id=issue.plan_id,
                    plan_artifact_path=plan_artifact_path,
                ),
            )
        else:
            note_path = self._write_artifact(
                category="developer",
                name=f"{agent_id}.md",
                content=(
                    f"Developer agent {agent_id} ran for issue #{issue.number}.\n\n"
                    "No external developer command is configured yet.\n"
                    "Set SOFTWARE_FACTORY_DEVELOPER_COMMAND to point to your Sandcastle wrapper.\n"
                ),
            )
            self.state_store.create_event(
                category="developer",
                message=f"Developer completed issue #{issue.number} without an external command",
                entity_type="issue",
                entity_id=str(issue.number),
                details={"artifact_path": str(note_path)},
            )

        branch = issue.branch_name or self.git.get_current_branch(workspace)
        commit_created = False
        if self.settings.git_workflow.auto_commit_changes:
            commit_created = self.git.commit_all(
                workspace,
                f"feat: resolve issue #{issue.number} - {issue.title}",
            )
            if commit_created:
                self.state_store.create_event(
                    category="developer",
                    message=f"Committed changes for issue #{issue.number}",
                    entity_type="issue",
                    entity_id=str(issue.number),
                    details={"branch_name": branch},
                )

        pull_request = self.state_store.find_pull_request_by_issue(issue.number)
        if commit_created:
            self.git.push_branch(workspace, branch)
            self.state_store.create_event(
                category="developer",
                message=f"Pushed branch {branch} for issue #{issue.number}",
                entity_type="issue",
                entity_id=str(issue.number),
                details={"branch_name": branch},
            )
        if pull_request is None and commit_created and self.settings.git_workflow.auto_create_pull_requests:
            pull_request = self.github.create_pull_request(
                title=f"Fix #{issue.number}: {issue.title}",
                body=self._build_pull_request_body(issue.number, issue.title, plan_artifact_path),
                head_branch=branch,
                base_branch=self.settings.git_workflow.default_branch,
                draft=self.settings.merge_policy.dry_run,
            )
            self.state_store.upsert_pull_request(pull_request)
            self.state_store.create_event(
                category="developer",
                message=f"Created PR #{pull_request.number} for issue #{issue.number}",
                entity_type="issue",
                entity_id=str(issue.number),
                details={"pull_request_number": pull_request.number, "branch_name": branch},
            )

        if pull_request is None:
            for item in self.github.list_pull_requests():
                self.state_store.upsert_pull_request(item)
                if item.issue_number == issue.number:
                    pull_request = item
                    break

        if pull_request is not None:
            issue.pull_request_number = pull_request.number
            issue.status = IssueStatus.REVIEW_PENDING
            issue.updated_at = datetime.now(UTC)
            self.state_store.upsert_issue(issue)

    def _run_reviewer(self, agent_id: str, pull_request_number: int | None) -> None:
        if pull_request_number is None:
            raise RuntimeError("Reviewer requires a pull request number")
        pull_request = self.state_store.get_pull_request(pull_request_number)
        if pull_request is None:
            raise RuntimeError(f"Unknown pull request #{pull_request_number}")

        review_output_path = self._artifact_path("reviews", f"pr-{pull_request.number}.md")
        if self.settings.commands.reviewer_command:
            self._run_external_command(
                command=self.settings.commands.reviewer_command,
                cwd=Path(self.settings.repository_path),
                agent_id=agent_id,
                extra_env=self._build_agent_env(
                    pull_request_number=pull_request.number,
                    pull_request_title=pull_request.title,
                    pull_request_body=pull_request.body,
                    branch_name=pull_request.branch_name,
                    review_output_path=str(review_output_path),
                ),
            )
        elif self.settings.merge_policy.auto_approve_pull_requests and not self.settings.merge_policy.dry_run:
            self.github.submit_pull_request_review(
                pull_request_number=pull_request.number,
                event="APPROVE",
                body="Approved by the software factory reviewer agent.",
            )
            pull_request.status = PullRequestStatus.APPROVED
            pull_request.review_summary = "Approved automatically by the software factory reviewer agent."
            pull_request.updated_at = datetime.now(UTC)
            self.state_store.upsert_pull_request(pull_request)
            if pull_request.issue_number is not None:
                issue = self.state_store.get_issue(pull_request.issue_number)
                if issue is not None:
                    issue.status = IssueStatus.APPROVED
                    issue.updated_at = datetime.now(UTC)
                    self.state_store.upsert_issue(issue)
        else:
            review_path = self._write_artifact(
                category="reviews",
                name=f"pr-{pull_request.number}.md",
                content=(
                    f"Reviewer agent {agent_id} inspected PR #{pull_request.number}.\n\n"
                    "No external reviewer command is configured, or dry-run mode is enabled.\n"
                ),
            )
            self.state_store.create_event(
                category="review",
                message=f"Reviewer completed dry review for PR #{pull_request.number}",
                entity_type="pull_request",
                entity_id=str(pull_request.number),
                details={"artifact_path": str(review_path)},
            )

    def _run_merger(self, agent_id: str, pull_request_number: int | None) -> None:
        if pull_request_number is None:
            raise RuntimeError("Merger requires a pull request number")
        pull_request = self.state_store.get_pull_request(pull_request_number)
        if pull_request is None:
            raise RuntimeError(f"Unknown pull request #{pull_request_number}")

        merge_record = self.state_store.get_merge(pull_request.number) or MergeRecord(
            pull_request_number=pull_request.number,
            issue_number=pull_request.issue_number,
        )
        merge_output_path = self._artifact_path("merges", f"pr-{pull_request.number}.md")
        if self.settings.commands.merger_command:
            self._run_external_command(
                command=self.settings.commands.merger_command,
                cwd=Path(self.settings.repository_path),
                agent_id=agent_id,
                extra_env=self._build_agent_env(
                    pull_request_number=pull_request.number,
                    pull_request_title=pull_request.title,
                    pull_request_body=pull_request.body,
                    branch_name=pull_request.branch_name,
                    merge_output_path=str(merge_output_path),
                ),
            )
        elif self.settings.merge_policy.auto_merge_pull_requests and not self.settings.merge_policy.dry_run:
            result = self.github.merge_pull_request(pull_request.number)
            if not result.get("merged"):
                raise RuntimeError(result.get("message") or f"Failed to merge PR #{pull_request.number}")
            merge_record.status = MergeStatus.MERGED
            merge_record.merged_at = datetime.now(UTC)
            merge_record.merge_commit_sha = result.get("sha")
            merge_record.details = result
            self.state_store.upsert_merge(merge_record)
            pull_request.status = PullRequestStatus.MERGED
            pull_request.merged_at = datetime.now(UTC)
            pull_request.merge_commit_sha = result.get("sha")
            self.state_store.upsert_pull_request(pull_request)
            if pull_request.issue_number is not None:
                issue = self.state_store.get_issue(pull_request.issue_number)
                if issue is not None:
                    issue.status = IssueStatus.MERGED
                    issue.updated_at = datetime.now(UTC)
                    self.state_store.upsert_issue(issue)
        else:
            merge_record.status = MergeStatus.READY
            self.state_store.upsert_merge(merge_record)
            merge_path = self._write_artifact(
                category="merges",
                name=f"pr-{pull_request.number}.md",
                content=(
                    f"Merger agent {agent_id} evaluated PR #{pull_request.number}.\n\n"
                    "No external merger command is configured, or dry-run mode is enabled.\n"
                ),
            )
            self.state_store.create_event(
                category="merge",
                message=f"Merger completed dry merge for PR #{pull_request.number}",
                entity_type="pull_request",
                entity_id=str(pull_request.number),
                details={"artifact_path": str(merge_path)},
            )

    def _run_external_command(
        self,
        command: str,
        cwd: Path,
        agent_id: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env=env,
        )
        if agent_id is not None:
            log_path = self._write_artifact(
                category="logs",
                name=f"{agent_id}.log",
                content=self._render_process_log(command, result.stdout, result.stderr),
            )
            agent = self.state_store.get_agent(agent_id)
            if agent is not None:
                agent.logs_path = str(log_path)
                agent.exit_code = result.returncode
                self.state_store.upsert_agent(agent)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"Command failed: {command}")

    def _heartbeat_loop(self, agent_id: str, stop_event: threading.Event) -> None:
        while not stop_event.wait(self.settings.agent_heartbeat_interval_seconds):
            agent = self.state_store.get_agent(agent_id)
            if agent is None:
                continue
            agent.heartbeat_at = datetime.now(UTC)
            self.state_store.upsert_agent(agent)

    def _build_agent_env(
        self,
        issue_number: int | None = None,
        issue_title: str | None = None,
        issue_body: str | None = None,
        pull_request_number: int | None = None,
        pull_request_title: str | None = None,
        pull_request_body: str | None = None,
        branch_name: str | None = None,
        plan_id: str | None = None,
        plan_artifact_path: str | None = None,
        review_output_path: str | None = None,
        merge_output_path: str | None = None,
    ) -> dict[str, str]:
        env: dict[str, str] = {
            "SOFTWARE_FACTORY_REPOSITORY_FULL_NAME": self.settings.repository_full_name,
            "SOFTWARE_FACTORY_DEFAULT_BRANCH": self.settings.git_workflow.default_branch,
        }
        optional_values = {
            "SOFTWARE_FACTORY_ISSUE_NUMBER": issue_number,
            "SOFTWARE_FACTORY_ISSUE_TITLE": issue_title,
            "SOFTWARE_FACTORY_ISSUE_BODY": issue_body,
            "SOFTWARE_FACTORY_PULL_REQUEST_NUMBER": pull_request_number,
            "SOFTWARE_FACTORY_PULL_REQUEST_TITLE": pull_request_title,
            "SOFTWARE_FACTORY_PULL_REQUEST_BODY": pull_request_body,
            "SOFTWARE_FACTORY_BRANCH_NAME": branch_name,
            "SOFTWARE_FACTORY_PLAN_ID": plan_id,
            "SOFTWARE_FACTORY_PLAN_ARTIFACT_PATH": plan_artifact_path,
            "SOFTWARE_FACTORY_REVIEW_OUTPUT_PATH": review_output_path,
            "SOFTWARE_FACTORY_MERGE_OUTPUT_PATH": merge_output_path,
        }
        for key, value in optional_values.items():
            if value is not None:
                env[key] = str(value)
        return env

    def _build_pull_request_body(self, issue_number: int, issue_title: str, plan_artifact_path: str | None) -> str:
        lines = [
            f"Closes #{issue_number}",
            "",
            f"Automated implementation for issue #{issue_number}: {issue_title}.",
        ]
        if plan_artifact_path:
            lines.extend(["", f"Plan artifact: `{plan_artifact_path}`"])
        return "\n".join(lines)

    def _render_process_log(self, command: str, stdout: str, stderr: str) -> str:
        return "\n".join(
            [
                f"$ {command}",
                "",
                "[stdout]",
                stdout.rstrip(),
                "",
                "[stderr]",
                stderr.rstrip(),
                "",
            ]
        )

    def _artifact_path(self, category: str, name: str) -> Path:
        directory = self.settings.runtime_paths.artifacts / category
        directory.mkdir(parents=True, exist_ok=True)
        return directory / name

    def _write_artifact(self, category: str, name: str, content: str) -> Path:
        artifact_path = self._artifact_path(category, name)
        artifact_path.write_text(content, encoding="utf-8")
        return artifact_path

