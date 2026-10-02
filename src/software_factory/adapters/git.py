import re
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from software_factory.settings import GitIdentitySettings, GitWorkflowSettings


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


@dataclass(slots=True)
class PreparedWorkspace:
    path: Path
    branch_name: str


class RepositoryNotReadyError(RuntimeError):
    """Raised when the repository does not yet have an initial commit."""


class GitWorkspaceAdapter:
    def __init__(self, repository_path: Path, identity: GitIdentitySettings, workflow: GitWorkflowSettings) -> None:
        self.repository_path = repository_path
        self.identity = identity
        self.workflow = workflow

    def repository_has_commits(self) -> bool:
        result = self._run(["git", "rev-parse", "--verify", "HEAD"], cwd=self.repository_path, check=False)
        return result.returncode == 0

    def ensure_repository_ready(self) -> None:
        if self.repository_has_commits():
            return
        raise RepositoryNotReadyError(
            "The repository has no commits yet. Run `python -m software_factory.cli bootstrap-repository` first."
        )

    def bootstrap_repository(self, push: bool = False) -> None:
        if self.repository_has_commits():
            return
        current_branch = self.get_current_branch(self.repository_path)
        if current_branch and current_branch not in {"HEAD", self.workflow.default_branch}:
            self._run(["git", "switch", "--orphan", self.workflow.default_branch], cwd=self.repository_path)
        self._run(["git", "add", "-A"], cwd=self.repository_path)
        self._run(
            ["git", "commit", "-m", self.workflow.bootstrap_commit_message],
            cwd=self.repository_path,
            env={
                "GIT_AUTHOR_NAME": self.identity.author_name,
                "GIT_AUTHOR_EMAIL": self.identity.author_email,
                "GIT_COMMITTER_NAME": self.identity.author_name,
                "GIT_COMMITTER_EMAIL": self.identity.author_email,
            },
        )
        if push:
            self.push_branch(self.repository_path, self.workflow.default_branch)

    def prepare_issue_workspace(self, issue_number: int, issue_title: str, workspace_root: Path, suffix: str) -> PreparedWorkspace:
        self.ensure_repository_ready()
        workspace_path = workspace_root / suffix / "repo"
        branch_name = self._build_branch_name(issue_number, issue_title, suffix)
        if not workspace_path.exists():
            workspace_path.parent.mkdir(parents=True, exist_ok=True)
            self._run(
                ["git", "clone", "--no-hardlinks", str(self.repository_path), str(workspace_path)],
                cwd=self.repository_path,
            )
            self._run(["git", "switch", "-c", branch_name], cwd=workspace_path)
            self._run(["git", "config", "user.name", self.identity.author_name], cwd=workspace_path)
            self._run(["git", "config", "user.email", self.identity.author_email], cwd=workspace_path)
        return PreparedWorkspace(path=workspace_path, branch_name=branch_name)

    def has_working_tree_changes(self, workspace_path: Path) -> bool:
        result = self._run(["git", "status", "--porcelain"], cwd=workspace_path, check=False)
        return bool(result.stdout.strip())

    def commit_all(self, workspace_path: Path, message: str) -> bool:
        if not self.has_working_tree_changes(workspace_path):
            return False
        self._run(["git", "add", "-A"], cwd=workspace_path)
        self._run(
            ["git", "commit", "-m", message],
            cwd=workspace_path,
            env={
                "GIT_AUTHOR_NAME": self.identity.author_name,
                "GIT_AUTHOR_EMAIL": self.identity.author_email,
                "GIT_COMMITTER_NAME": self.identity.author_name,
                "GIT_COMMITTER_EMAIL": self.identity.author_email,
            },
        )
        return True

    def push_branch(self, workspace_path: Path, branch_name: str) -> None:
        self._run(
            ["git", "push", "-u", self.workflow.remote_name, f"HEAD:{branch_name}"],
            cwd=workspace_path,
        )

    def get_current_branch(self, workspace_path: Path) -> str:
        result = self._run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace_path,
            check=False,
        )
        return result.stdout.strip()

    def _build_branch_name(self, issue_number: int, issue_title: str, suffix: str) -> str:
        title_slug = slugify(issue_title)[:24] or f"issue-{issue_number}"
        return f"factory/issue-{issue_number}-{title_slug}-{suffix}"[:120]

    def _run(
        self,
        command: list[str],
        cwd: Path,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged_env = None
        if env is not None:
            merged_env = os.environ.copy()
            merged_env.update(env)
        return subprocess.run(
            command,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
            env=merged_env,
        )
