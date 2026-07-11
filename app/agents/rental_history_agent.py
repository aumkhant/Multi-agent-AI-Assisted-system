from semantic_kernel import Kernel
from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome
from app.schemas import GetCustomerRentalHistoryInput
from app.tools.rental_history import get_customer_rental_history
from app.utils.llm import complete_chat

_SYSTEM_PROMPT = """You are RentalHistoryAgent for a streaming and rental platform. You are
given the customer's recent rentals as JSON. Summarize them (title and dates) in 1-3
customer-friendly sentences, using ONLY that data. If the list is empty, say they have no
recent rental history. Never invent rentals not present in the JSON.
"""


async def handle(
    kernel: Kernel, session: Session, conversation_id: str, message: str, customer_id: int | None
) -> AgentOutcome:
    if customer_id is None:
        return AgentOutcome(
            answer="I need your customer ID to look up rental history. Could you share it?",
            tools_used=[],
            citations=[],
            next_action="await_customer_id",
        )

    result = get_customer_rental_history(
        session, conversation_id, GetCustomerRentalHistoryInput(customer_id=customer_id)
    )

    user_prompt = f"Customer question: {message}\n\nRental history (JSON): {result.model_dump_json()}"
    answer = await complete_chat(kernel, _SYSTEM_PROMPT, user_prompt)

    return AgentOutcome(
        answer=answer,
        tools_used=["get_customer_rental_history"],
        citations=[],
        next_action="none",
    )
