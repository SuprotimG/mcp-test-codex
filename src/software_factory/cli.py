import typer

from software_factory.adapters.git import GitWorkspaceAdapter
from software_factory.bootstrap import build_runtime
from software_factory.domain.enums import AgentRole
from software_factory.services.agent_runtime import AgentRuntimeService
from software_factory.services.scheduler import Scheduler

app = typer.Typer(no_args_is_help=True)


def main() -> None:
    app()


@app.command("run-scheduler")
def run_scheduler() -> None:
    runtime = build_runtime()
    scheduler = Scheduler(
        coordinator=runtime.coordinator,
        poll_interval_seconds=runtime.settings.scheduler_poll_interval_seconds,
    )
    scheduler.run_forever()


@app.command("run-once")
def run_once() -> None:
    runtime = build_runtime()
    runtime.coordinator.run_once()


@app.command("sync")
def sync() -> None:
    runtime = build_runtime()
    runtime.coordinator.sync()


@app.command("bootstrap-repository")
def bootstrap_repository(
    push: bool = typer.Option(False, help="Push the initial branch to origin after creating the first commit."),
) -> None:
    runtime = build_runtime()
    git = GitWorkspaceAdapter(runtime.settings.repository_path, runtime.settings.git_identity, runtime.settings.git_workflow)
    git.bootstrap_repository(push=push)


@app.command("run-worker")
def run_worker() -> None:
    typer.echo("Use `run-agent` for role-specific execution.")


@app.command("run-agent")
def run_agent(
    role: str = typer.Option(...),
    agent_id: str = typer.Option(...),
    issue_number: int | None = typer.Option(None),
    pull_request_number: int | None = typer.Option(None),
    plan_id: str | None = typer.Option(None),
    workspace_path: str | None = typer.Option(None),
    branch_name: str | None = typer.Option(None),
) -> None:
    runtime = build_runtime()
    runner = AgentRuntimeService(runtime.settings, runtime.state_store)
    exit_code = runner.run(
        role=AgentRole(role),
        agent_id=agent_id,
        issue_number=issue_number,
        pull_request_number=pull_request_number,
        plan_id=plan_id,
        workspace_path=workspace_path,
        branch_name=branch_name,
    )
    raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    main()
