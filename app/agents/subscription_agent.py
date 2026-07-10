from semantic_kernel import Kernel
from sqlalchemy.orm import Session

from app.agents.base import AgentOutcome
from app.agents.llm import complete_chat
from app.tools.base import ToolError
from app.tools.subscription import GetCustomerStreamingSubscriptionInput, get_customer_streaming_subscription

_SYSTEM_PROMPT = """You are SubscriptionAgent for a streaming and rental platform. You are
given the customer's subscription record as JSON. Answer using ONLY that data - plan name,
status, renewal date, and auto-renew. Keep the answer to 1-3 sentences, customer-friendly.
Never invent subscription details not present in the JSON.
"""


async def handle(
    kernel: Kernel, session: Session, conversation_id: str, message: str, customer_id: int | None
) -> AgentOutcome:
    if customer_id is None:
        return AgentOutcome(
            answer="I need your customer ID to look up subscription status. Could you share it?",
            tools_used=[],
            citations=[],
            next_action="await_customer_id",
        )

    try:
        result = get_customer_streaming_subscription(
            session, conversation_id, GetCustomerStreamingSubscriptionInput(customer_id=customer_id)
        )
    except ToolError:
        return AgentOutcome(
            answer="I couldn't find an active streaming subscription on your account.",
            tools_used=["get_customer_streaming_subscription"],
            citations=[],
            next_action="none",
        )

    user_prompt = f"Customer question: {message}\n\nSubscription record (JSON): {result.model_dump_json()}"
    answer = await complete_chat(kernel, _SYSTEM_PROMPT, user_prompt)

    return AgentOutcome(
        answer=answer,
        tools_used=["get_customer_streaming_subscription"],
        citations=[],
        next_action="none",
    )
