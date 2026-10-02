import os
from pathlib import Path

from pydantic import BaseModel, Field


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


class RuntimePaths(BaseModel):
    root: Path = Field(default=Path("var"))
    state: Path = Field(default=Path("var/state"))
    artifacts: Path = Field(default=Path("var/artifacts"))
    workspaces: Path = Field(default=Path("var/workspaces"))


class GitHubSettings(BaseModel):
    api_url: str = Field(default="https://api.github.com")
    token: str | None = None
    issues_per_page: int = Field(default=100)
    pulls_per_page: int = Field(default=100)


class PodmanSettings(BaseModel):
    executable: str = Field(default="podman")
    worker_image: str = Field(default="localhost/software-factory-worker:latest")
    network: str = Field(default="bridge")
    container_repository_path: str = Field(default="/workspace")
    container_state_path: str = Field(default="/factory-state")
    container_artifacts_path: str = Field(default="/factory-artifacts")


class CommandProfiles(BaseModel):
    planner_command: str | None = None
    developer_command: str | None = None
    reviewer_command: str | None = None
    merger_command: str | None = None


class MergePolicySettings(BaseModel):
    auto_approve_pull_requests: bool = Field(default=False)
    auto_merge_pull_requests: bool = Field(default=False)
    merge_method: str = Field(default="squash")
    dry_run: bool = Field(default=True)


class GitIdentitySettings(BaseModel):
    author_name: str = Field(default="Software Factory")
    author_email: str = Field(default="software-factory@example.com")


class GitWorkflowSettings(BaseModel):
    default_branch: str = Field(default="main")
    remote_name: str = Field(default="origin")
    auto_commit_changes: bool = Field(default=True)
    auto_create_pull_requests: bool = Field(default=True)
    bootstrap_commit_message: str = Field(default="chore: bootstrap autonomous software factory")


class Settings(BaseModel):
    repository_owner: str = Field(default="SuprotimG")
    repository_name: str = Field(default="mcp-test-codex")
    repository_path: Path = Field(default_factory=lambda: Path.cwd())
    max_parallel_workers: int = Field(default=4)
    scheduler_poll_interval_seconds: int = Field(default=15)
    agent_heartbeat_interval_seconds: int = Field(default=5)
    runtime_paths: RuntimePaths = Field(default_factory=RuntimePaths)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    podman: PodmanSettings = Field(default_factory=PodmanSettings)
    commands: CommandProfiles = Field(default_factory=CommandProfiles)
    merge_policy: MergePolicySettings = Field(default_factory=MergePolicySettings)
    git_identity: GitIdentitySettings = Field(default_factory=GitIdentitySettings)
    git_workflow: GitWorkflowSettings = Field(default_factory=GitWorkflowSettings)

    @property
    def repository_full_name(self) -> str:
        return f"{self.repository_owner}/{self.repository_name}"


def get_settings() -> Settings:
    runtime_root = Path(os.getenv("SOFTWARE_FACTORY_RUNTIME_ROOT", "var"))
    runtime_state = Path(os.getenv("SOFTWARE_FACTORY_RUNTIME_STATE", runtime_root / "state"))
    runtime_artifacts = Path(os.getenv("SOFTWARE_FACTORY_RUNTIME_ARTIFACTS", runtime_root / "artifacts"))
    runtime_workspaces = Path(os.getenv("SOFTWARE_FACTORY_RUNTIME_WORKSPACES", runtime_root / "workspaces"))

    return Settings(
        repository_owner=os.getenv("SOFTWARE_FACTORY_REPOSITORY_OWNER", "SuprotimG"),
        repository_name=os.getenv("SOFTWARE_FACTORY_REPOSITORY_NAME", "mcp-test-codex"),
        repository_path=Path(os.getenv("SOFTWARE_FACTORY_REPOSITORY_PATH", Path.cwd())),
        max_parallel_workers=env_int("SOFTWARE_FACTORY_MAX_PARALLEL_WORKERS", 4),
        scheduler_poll_interval_seconds=env_int("SOFTWARE_FACTORY_SCHEDULER_POLL_INTERVAL_SECONDS", 15),
        agent_heartbeat_interval_seconds=env_int("SOFTWARE_FACTORY_AGENT_HEARTBEAT_INTERVAL_SECONDS", 5),
        runtime_paths=RuntimePaths(
            root=runtime_root,
            state=runtime_state,
            artifacts=runtime_artifacts,
            workspaces=runtime_workspaces,
        ),
        github=GitHubSettings(
            api_url=os.getenv("SOFTWARE_FACTORY_GITHUB_API_URL", "https://api.github.com"),
            token=os.getenv("SOFTWARE_FACTORY_GITHUB_TOKEN"),
            issues_per_page=env_int("SOFTWARE_FACTORY_GITHUB_ISSUES_PER_PAGE", 100),
            pulls_per_page=env_int("SOFTWARE_FACTORY_GITHUB_PULLS_PER_PAGE", 100),
        ),
        podman=PodmanSettings(
            executable=os.getenv("SOFTWARE_FACTORY_PODMAN_EXECUTABLE", "podman"),
            worker_image=os.getenv("SOFTWARE_FACTORY_WORKER_IMAGE", "localhost/software-factory-worker:latest"),
            network=os.getenv("SOFTWARE_FACTORY_PODMAN_NETWORK", "bridge"),
            container_repository_path=os.getenv("SOFTWARE_FACTORY_CONTAINER_REPOSITORY_PATH", "/workspace"),
            container_state_path=os.getenv("SOFTWARE_FACTORY_CONTAINER_STATE_PATH", "/factory-state"),
            container_artifacts_path=os.getenv("SOFTWARE_FACTORY_CONTAINER_ARTIFACTS_PATH", "/factory-artifacts"),
        ),
        commands=CommandProfiles(
            planner_command=os.getenv("SOFTWARE_FACTORY_PLANNER_COMMAND"),
            developer_command=os.getenv("SOFTWARE_FACTORY_DEVELOPER_COMMAND"),
            reviewer_command=os.getenv("SOFTWARE_FACTORY_REVIEWER_COMMAND"),
            merger_command=os.getenv("SOFTWARE_FACTORY_MERGER_COMMAND"),
        ),
        merge_policy=MergePolicySettings(
            auto_approve_pull_requests=env_bool("SOFTWARE_FACTORY_AUTO_APPROVE_PULL_REQUESTS", False),
            auto_merge_pull_requests=env_bool("SOFTWARE_FACTORY_AUTO_MERGE_PULL_REQUESTS", False),
            merge_method=os.getenv("SOFTWARE_FACTORY_MERGE_METHOD", "squash"),
            dry_run=env_bool("SOFTWARE_FACTORY_DRY_RUN", True),
        ),
        git_identity=GitIdentitySettings(
            author_name=os.getenv("SOFTWARE_FACTORY_GIT_AUTHOR_NAME", "Software Factory"),
            author_email=os.getenv("SOFTWARE_FACTORY_GIT_AUTHOR_EMAIL", "software-factory@example.com"),
        ),
        git_workflow=GitWorkflowSettings(
            default_branch=os.getenv("SOFTWARE_FACTORY_DEFAULT_BRANCH", "main"),
            remote_name=os.getenv("SOFTWARE_FACTORY_PUSH_REMOTE_NAME", "origin"),
            auto_commit_changes=env_bool("SOFTWARE_FACTORY_AUTO_COMMIT_CHANGES", True),
            auto_create_pull_requests=env_bool("SOFTWARE_FACTORY_AUTO_CREATE_PULL_REQUESTS", True),
            bootstrap_commit_message=os.getenv(
                "SOFTWARE_FACTORY_BOOTSTRAP_COMMIT_MESSAGE",
                "chore: bootstrap autonomous software factory",
            ),
        ),
    )
