from semantic_kernel import Kernel
from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome
from app.schemas import SearchFilmCatalogInput
from app.tools.catalog import search_film_catalog
from app.utils.llm import complete_chat
from app.utils.query_extraction import extract_title_query

_SYSTEM_PROMPT = """You are CatalogAgent, a customer-friendly assistant for a streaming and
rental platform. You are given search results from the film catalog as JSON. Answer the
customer's question using ONLY that data - title, category, rating, rental rate, and
streaming availability. If the results are empty, say the film could not be found in the
catalog. Keep the answer to 1-3 sentences. Never invent films or data not present in the JSON.
"""


async def handle(
    kernel: Kernel, session: Session, conversation_id: str, message: str
) -> AgentOutcome:
    query = extract_title_query(message)
    result = search_film_catalog(session, conversation_id, SearchFilmCatalogInput(query=query))

    user_prompt = f"Customer question: {message}\n\nCatalog search results (JSON): {result.model_dump_json()}"
    answer = await complete_chat(kernel, _SYSTEM_PROMPT, user_prompt)

    return AgentOutcome(
        answer=answer,
        tools_used=["search_film_catalog"],
        citations=[],
        next_action="none",
    )
