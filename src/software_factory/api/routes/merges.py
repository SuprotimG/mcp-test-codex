from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/merges", tags=["merges"])


@router.get("")
def list_merges(request: Request) -> list[dict]:
    merges = request.app.state.runtime.state_store.list_merges()
    return [merge.model_dump(mode="json") for merge in merges]

