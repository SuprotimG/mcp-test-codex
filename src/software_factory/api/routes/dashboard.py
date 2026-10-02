from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    snapshot = request.app.state.runtime.state_store.get_dashboard_snapshot()
    return templates.TemplateResponse(
        name="dashboard.html",
        context={"request": request, "snapshot": snapshot},
    )



@router.get("/api/dashboard")
def dashboard_json(request: Request) -> dict:
    snapshot = request.app.state.runtime.state_store.get_dashboard_snapshot()
    return snapshot.model_dump(mode="json")
