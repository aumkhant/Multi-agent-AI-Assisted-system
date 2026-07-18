from app.agents.base import AgentOutcome
from app.mcp_client import call_tool
from app.schemas import CreateHandoffTicketOutput


async def handle(conversation_id: str, message: str, reason: str) -> AgentOutcome:
    """Creates a handoff ticket and lets the customer know a human will follow up.
    Never performs an account mutation itself - only the human agent does."""
    result = await call_tool(
        "create_handoff_ticket",
        conversation_id,
        {"summary": message, "reason": reason},
        CreateHandoffTicketOutput,
    )

    answer = (
        "I've created a ticket for a human support agent to help with this "
        f"(ticket {result.ticket_id}). They'll follow up with you shortly. I'm not able to "
        "make account or billing changes directly."
    )

    return AgentOutcome(
        answer=answer,
        tools_used=["create_handoff_ticket"],
        citations=[],
        next_action="handoff_created",
    )
