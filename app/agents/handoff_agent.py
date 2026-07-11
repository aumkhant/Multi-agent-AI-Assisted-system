from app.agents.base import AgentOutcome
from app.schemas import CreateHandoffTicketInput
from app.tools.handoff import create_handoff_ticket


def handle(conversation_id: str, message: str, reason: str) -> AgentOutcome:
    """Creates a handoff ticket and lets the customer know a human will follow up.
    Never performs an account mutation itself - only the human agent does."""
    result = create_handoff_ticket(
        conversation_id, CreateHandoffTicketInput(summary=message, reason=reason)
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
