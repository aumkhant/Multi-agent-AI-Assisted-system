from semantic_kernel import Kernel

from app.agents.base import AgentOutcome
from app.mcp_client import call_tool
from app.schemas import SearchWebOutput
from app.utils.llm import complete_chat

_SYSTEM_PROMPT = """You are WebSearchAgent. You are given public web search results as JSON.
Answer the user's question using ONLY that data, in 1-3 sentences, and mention the most
relevant source by title. If the results are empty, say that you couldn't find a reliable
public-web answer. Never invent facts not present in the JSON.
"""


async def handle(kernel: Kernel, conversation_id: str, message: str) -> AgentOutcome:
    result = await call_tool(
        "search_web",
        conversation_id,
        {"query": message},
        SearchWebOutput,
    )

    if not result.results:
        return AgentOutcome(
            answer="I couldn't find a reliable public-web answer for that.",
            tools_used=["search_web"],
            citations=[],
            next_action="none",
            answered=False,
        )

    user_prompt = f"User question: {message}\n\nWeb search results (JSON): {result.model_dump_json()}"
    answer = await complete_chat(kernel, _SYSTEM_PROMPT, user_prompt)
    return AgentOutcome(
        answer=answer,
        tools_used=["search_web"],
        citations=[item.url for item in result.results],
        next_action="none",
    )
