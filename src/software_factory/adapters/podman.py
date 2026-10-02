import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from software_factory.domain.enums import AgentRole
from software_factory.settings import Settings


def sanitize_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", value)


@dataclass(slots=True)
class ContainerRunRequest:
    agent_id: str
    role: AgentRole
    issue_number: int | None = None
    pull_request_number: int | None = None
    plan_id: str | None = None
    workspace_path: str | None = None
    branch_name: str | None = None


@dataclass(slots=True)
class ContainerExecutionResult:
    container_name: str
    exit_code: int
    stdout: str
    stderr: str


class PodmanAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def start_agent_container(self, request: ContainerRunRequest) -> str:
        self._ensure_podman_available()
        container_name = self._build_container_name(request)
        command = self._build_run_command(request, container_name=container_name, detach=True)
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return container_name if result.stdout.strip() else container_name

    def run_agent_once(self, request: ContainerRunRequest) -> ContainerExecutionResult:
        self._ensure_podman_available()
        container_name = self._build_container_name(request)
        command = self._build_run_command(request, container_name=container_name, detach=False, remove=True)
        result = subprocess.run(command, capture_output=True, text=True)
        return ContainerExecutionResult(
            container_name=container_name,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def inspect_container(self, container_name: str) -> dict[str, Any] | None:
        self._ensure_podman_available()
        result = subprocess.run(
            [self.settings.podman.executable, "inspect", container_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout)
        if not payload:
            return None
        return payload[0]

    def stop_agent_container(self, container_name: str) -> None:
        self._ensure_podman_available()
        subprocess.run([self.settings.podman.executable, "rm", "-f", container_name], check=False)

    def _ensure_podman_available(self) -> None:
        if shutil.which(self.settings.podman.executable) is None:
            raise RuntimeError(f"{self.settings.podman.executable} is not installed or not on PATH")

    def _build_container_name(self, request: ContainerRunRequest) -> str:
        issue_fragment = request.issue_number if request.issue_number is not None else "system"
        return sanitize_name(f"sf-{request.role.value}-{issue_fragment}-{request.agent_id}")

    def _build_run_command(
        self,
        request: ContainerRunRequest,
        container_name: str,
        detach: bool,
        remove: bool = False,
    ) -> list[str]:
        repository_path = Path(request.workspace_path) if request.workspace_path else self.settings.repository_path
        command = [self.settings.podman.executable, "run", "--name", container_name]
        if detach:
            command.append("-d")
        if remove:
            command.append("--rm")
        command.extend(
            [
                "--label",
                "software-factory.managed=true",
                "--label",
                f"software-factory.role={request.role.value}",
                "--label",
                f"software-factory.agent_id={request.agent_id}",
                "--network",
                self.settings.podman.network,
                "-w",
                self.settings.podman.container_repository_path,
                "-v",
                f"{repository_path}:{self.settings.podman.container_repository_path}",
                "-v",
                f"{self.settings.runtime_paths.state}:{self.settings.podman.container_state_path}",
                "-v",
                f"{self.settings.runtime_paths.artifacts}:{self.settings.podman.container_artifacts_path}",
            ]
        )
        if request.issue_number is not None:
            command.extend(["-e", f"SOFTWARE_FACTORY_ISSUE_NUMBER={request.issue_number}"])
        if request.pull_request_number is not None:
            command.extend(["-e", f"SOFTWARE_FACTORY_PULL_REQUEST_NUMBER={request.pull_request_number}"])
        if request.plan_id is not None:
            command.extend(["-e", f"SOFTWARE_FACTORY_PLAN_ID={request.plan_id}"])
        if request.branch_name is not None:
            command.extend(["-e", f"SOFTWARE_FACTORY_BRANCH_NAME={request.branch_name}"])
        command.extend(["-e", f"SOFTWARE_FACTORY_AGENT_ID={request.agent_id}"])
        command.extend(["-e", f"SOFTWARE_FACTORY_ROLE={request.role.value}"])
        command.extend(["-e", f"SOFTWARE_FACTORY_REPOSITORY_PATH={self.settings.podman.container_repository_path}"])
        command.extend(["-e", f"SOFTWARE_FACTORY_RUNTIME_STATE={self.settings.podman.container_state_path}"])
        command.extend(["-e", f"SOFTWARE_FACTORY_RUNTIME_ARTIFACTS={self.settings.podman.container_artifacts_path}"])
        command.extend(["-e", "SOFTWARE_FACTORY_RUNTIME_WORKSPACES=/factory-workspaces"])
        command.extend(["-e", "SOFTWARE_FACTORY_RUNTIME_ROOT=/factory-root"])

        for name, value in os.environ.items():
            if name.startswith("SOFTWARE_FACTORY_") and name not in {
                "SOFTWARE_FACTORY_AGENT_ID",
                "SOFTWARE_FACTORY_ROLE",
                "SOFTWARE_FACTORY_ISSUE_NUMBER",
                "SOFTWARE_FACTORY_PULL_REQUEST_NUMBER",
                "SOFTWARE_FACTORY_PLAN_ID",
                "SOFTWARE_FACTORY_BRANCH_NAME",
                "SOFTWARE_FACTORY_REPOSITORY_PATH",
                "SOFTWARE_FACTORY_RUNTIME_STATE",
                "SOFTWARE_FACTORY_RUNTIME_ARTIFACTS",
                "SOFTWARE_FACTORY_RUNTIME_WORKSPACES",
                "SOFTWARE_FACTORY_RUNTIME_ROOT",
            }:
                command.extend(["-e", f"{name}={value}"])

        command.append(self.settings.podman.worker_image)
        command.extend(
            [
                "python",
                "-m",
                "software_factory.cli",
                "run-agent",
                "--role",
                request.role.value,
                "--agent-id",
                request.agent_id,
            ]
        )
        if request.issue_number is not None:
            command.extend(["--issue-number", str(request.issue_number)])
        if request.pull_request_number is not None:
            command.extend(["--pull-request-number", str(request.pull_request_number)])
        if request.plan_id is not None:
            command.extend(["--plan-id", request.plan_id])
        if request.workspace_path is not None:
            command.extend(["--workspace-path", self.settings.podman.container_repository_path])
        if request.branch_name is not None:
            command.extend(["--branch-name", request.branch_name])
        return command

