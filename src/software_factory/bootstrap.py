from dataclasses import dataclass
from pathlib import Path

from software_factory.adapters.state_store import LocalStateStore
from software_factory.config import ensure_runtime_directories
from software_factory.services.coordinator import Coordinator
from software_factory.settings import Settings, get_settings


@dataclass(slots=True)
class Runtime:
    settings: Settings
    state_store: LocalStateStore
    coordinator: Coordinator


def build_runtime() -> Runtime:
    settings = get_settings()
    ensure_runtime_directories(settings)
    state_store = LocalStateStore(Path(settings.runtime_paths.state) / "factory.db")
    coordinator = Coordinator(settings=settings, state_store=state_store)
    return Runtime(settings=settings, state_store=state_store, coordinator=coordinator)

