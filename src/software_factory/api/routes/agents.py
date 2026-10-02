from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def list_agents(request: Request) -> list[dict]:
    agents = request.app.state.runtime.state_store.list_agents()
    return [agent.model_dump(mode="json") for agent in agents]

