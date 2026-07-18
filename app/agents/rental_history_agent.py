from semantic_kernel import Kernel

from app.agents.base import AgentOutcome
from app.mcp_client import call_tool
from app.schemas import GetCustomerRentalHistoryOutput
from app.utils.llm import complete_chat

_SYSTEM_PROMPT = """You are RentalHistoryAgent for a streaming and rental platform. You are
given the customer's recent rentals as JSON. Summarize them (title and dates) in 1-3
customer-friendly sentences, using ONLY that data. If the list is empty, say they have no
recent rental history. Never invent rentals not present in the JSON.
"""


async def handle(
    kernel: Kernel, conversation_id: str, message: str, customer_id: int | None
) -> AgentOutcome:
    if customer_id is None:
        return AgentOutcome(
            answer="I need your customer ID to look up rental history. Could you share it?",
            tools_used=[],
            citations=[],
            next_action="await_customer_id",
        )

    result = await call_tool(
        "get_customer_rental_history",
        conversation_id,
        {"customer_id": customer_id},
        GetCustomerRentalHistoryOutput,
    )

    if not result.rentals:
        return AgentOutcome(
            answer="I couldn't find any rental history details to answer that from our records.",
            tools_used=["get_customer_rental_history"],
            citations=[],
            next_action="none",
            answered=False,
        )

    user_prompt = f"Customer question: {message}\n\nRental history (JSON): {result.model_dump_json()}"
    answer = await complete_chat(kernel, _SYSTEM_PROMPT, user_prompt)

    return AgentOutcome(
        answer=answer,
        tools_used=["get_customer_rental_history"],
        citations=[],
        next_action="none",
    )
