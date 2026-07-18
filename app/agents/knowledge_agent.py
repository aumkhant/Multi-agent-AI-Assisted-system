from semantic_kernel import Kernel

from app.agents.base import AgentOutcome
from app.mcp_client import call_tool
from app.schemas import SearchKbOutput
from app.utils.llm import complete_chat

_SYSTEM_PROMPT = """You are KnowledgeAgent for a streaming and rental platform's support
desk. You are given knowledge-base search results as JSON. Answer using ONLY that data,
in 1-3 sentences, and mention which article(s) you used by title. If the results are
empty, clearly say the knowledge base does not contain an answer to this question and
suggest a human handoff. Never invent information not present in the JSON.
"""


async def handle(kernel: Kernel, conversation_id: str, message: str) -> AgentOutcome:
    result = await call_tool(
        "search_kb",
        conversation_id,
        {"query": message},
        SearchKbOutput,
    )

    if not result.articles:
        return AgentOutcome(
            answer="I couldn't find anything in our knowledge base that answers that directly.",
            tools_used=["search_kb"],
            citations=[],
            next_action="none",
            answered=False,
        )

    user_prompt = f"Customer question: {message}\n\nKB search results (JSON): {result.model_dump_json()}"
    answer = await complete_chat(kernel, _SYSTEM_PROMPT, user_prompt)

    # Check if the LLM indicates no relevant answer was found in the KB
    # This handles cases where KB search found articles but they don't match the query
    answer_lower = answer.lower()
    is_unanswered = (
        "does not contain" in answer_lower
        or "no information" in answer_lower
        or "cannot find" in answer_lower
        or "couldn't find" in answer_lower
    )

    return AgentOutcome(
        answer=answer,
        tools_used=["search_kb"],
        citations=[article.source for article in result.articles] if not is_unanswered else [],
        next_action="none",
        answered=not is_unanswered,
    )
