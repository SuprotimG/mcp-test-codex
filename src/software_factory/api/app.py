from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from software_factory.api.routes import agents, dashboard, health, issues, merges, pulls
from software_factory.bootstrap import build_runtime

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def create_app() -> FastAPI:
    runtime = build_runtime()
    app = FastAPI(title="Autonomous Software Factory MVP")
    app.state.runtime = runtime
    app.mount("/static", StaticFiles(directory=str(PACKAGE_ROOT / "static")), name="static")
    app.include_router(health.router)
    app.include_router(dashboard.router)
    app.include_router(issues.router)
    app.include_router(agents.router)
    app.include_router(pulls.router)
    app.include_router(merges.router)
    return app

