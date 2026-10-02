from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/pulls", tags=["pulls"])


@router.get("")
def list_pulls(request: Request) -> list[dict]:
    pulls = request.app.state.runtime.state_store.list_pull_requests()
    return [pull_request.model_dump(mode="json") for pull_request in pulls]

