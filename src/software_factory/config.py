from pathlib import Path

from software_factory.settings import Settings


def ensure_runtime_directories(settings: Settings) -> None:
    for path in (
        settings.runtime_paths.root,
        settings.runtime_paths.state,
        settings.runtime_paths.artifacts,
        settings.runtime_paths.workspaces,
    ):
        Path(path).mkdir(parents=True, exist_ok=True)

