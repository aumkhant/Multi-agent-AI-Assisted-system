from semantic_kernel import Kernel

from app.agents.base import AgentOutcome
from app.agents.llm import complete_chat
from app.schemas import SearchKbInput
from app.tools.knowledge_base import search_kb

_SYSTEM_PROMPT = """You are KnowledgeAgent for a streaming and rental platform's support
desk. You are given knowledge-base search results as JSON. Answer using ONLY that data,
in 1-3 sentences, and mention which article(s) you used by title. If the results are
empty, clearly say the knowledge base does not contain an answer to this question and
suggest a human handoff. Never invent information not present in the JSON.
"""


async def handle(kernel: Kernel, conversation_id: str, message: str) -> AgentOutcome:
    result = search_kb(conversation_id, SearchKbInput(query=message))

    if not result.articles:
        return AgentOutcome(
            answer="I couldn't find anything in our knowledge base about that. I'd recommend "
            "requesting a human handoff for this question.",
            tools_used=["search_kb"],
            citations=[],
            next_action="none",
        )

    user_prompt = f"Customer question: {message}\n\nKB search results (JSON): {result.model_dump_json()}"
    answer = await complete_chat(kernel, _SYSTEM_PROMPT, user_prompt)

    return AgentOutcome(
        answer=answer,
        tools_used=["search_kb"],
        citations=[article.source for article in result.articles],
        next_action="none",
    )
