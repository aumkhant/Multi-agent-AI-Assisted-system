import logging

from fastapi import Depends, FastAPI
from semantic_kernel import Kernel

from app.agents.llm import build_kernel
from app.orchestrator import handle_request
from app.schemas import AgentRequest, AgentResponse

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Multi-Agent Support Assistant")

_kernel: Kernel | None = None


def get_kernel() -> Kernel:
    """Lazily builds the Semantic Kernel instance on first use, so importing the app
    (e.g. for tests) doesn't require an OpenAI API key to be configured."""
    global _kernel
    if _kernel is None:
        _kernel = build_kernel()
    return _kernel


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/respond", response_model=AgentResponse)
async def agent_respond(
    request: AgentRequest, kernel: Kernel = Depends(get_kernel)
) -> AgentResponse:
    return await handle_request(
        kernel, request.conversation_id, request.message, request.customer_id
    )
