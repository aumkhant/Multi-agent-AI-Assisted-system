import itertools
import threading
from datetime import datetime, timezone

from app.schemas import CreateHandoffTicketInput, CreateHandoffTicketOutput
from app.tools.base import ToolMetadata, logged_tool_call


METADATA = ToolMetadata(
    name="create_handoff_ticket",
    description="Simulate creating an escalation ticket for a human support agent. Does not "
    "perform any account mutation.",
    input_schema=CreateHandoffTicketInput.model_json_schema(),
    output_schema=CreateHandoffTicketOutput.model_json_schema(),
    error_behavior="Never raises; always returns a created ticket.",
    auth_requirement="none (creates a ticket record, does not read or change account state)",
    ownership_boundary="Writes only to the in-memory ticket store; never touches customer "
    "account data directly.",
    backed_by="mock (in-memory)",
)

_lock = threading.Lock()
_counter = itertools.count(1)
_tickets: list[dict] = []


def create_handoff_ticket(
    conversation_id: str, params: CreateHandoffTicketInput
) -> CreateHandoffTicketOutput:
    with logged_tool_call("create_handoff_ticket", conversation_id):
        with _lock:
            ticket_id = f"HAND-{next(_counter):05d}"
            record = {
                "ticket_id": ticket_id,
                "conversation_id": conversation_id,
                "summary": params.summary,
                "reason": params.reason,
                "status": "open",
                "created_at": datetime.now(timezone.utc),
            }
            _tickets.append(record)
        return CreateHandoffTicketOutput(
            ticket_id=record["ticket_id"],
            status=record["status"],
            created_at=record["created_at"],
        )


def list_tickets() -> list[dict]:
    """Test/debug helper to inspect tickets created during a process lifetime."""
    with _lock:
        return list(_tickets)
