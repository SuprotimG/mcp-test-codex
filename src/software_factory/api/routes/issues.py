from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("")
def list_issues(request: Request) -> list[dict]:
    issues = request.app.state.runtime.state_store.list_issues()
    return [issue.model_dump(mode="json") for issue in issues]

