import itertools
import threading
from datetime import datetime, timezone

from app.schemas import (
    CreateHandoffTicketInput,
    CreateHandoffTicketOutput,
    DeleteHandoffTicketInput,
    DeleteHandoffTicketOutput,
    GetHandoffTicketInput,
    GetHandoffTicketOutput,
    HandoffTicketRecord,
    ListHandoffTicketsInput,
    ListHandoffTicketsOutput,
    UpdateHandoffTicketInput,
    UpdateHandoffTicketOutput,
)
from app.tools.base import ToolError, ToolMetadata, logged_tool_call


CREATE_METADATA = ToolMetadata(
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

GET_METADATA = ToolMetadata(
    name="get_handoff_ticket",
    description="Get a single human handoff ticket by ticket ID.",
    input_schema=GetHandoffTicketInput.model_json_schema(),
    output_schema=GetHandoffTicketOutput.model_json_schema(),
    error_behavior="Raises ToolError(code='not_found') when the ticket does not exist.",
    auth_requirement="none (reads only from the in-memory ticket store)",
    ownership_boundary="Reads only from the in-memory ticket store.",
    backed_by="mock (in-memory)",
)

LIST_METADATA = ToolMetadata(
    name="list_handoff_tickets",
    description="List handoff tickets, optionally filtered by status.",
    input_schema=ListHandoffTicketsInput.model_json_schema(),
    output_schema=ListHandoffTicketsOutput.model_json_schema(),
    error_behavior="Returns an empty tickets list when no tickets match.",
    auth_requirement="none (reads only from the in-memory ticket store)",
    ownership_boundary="Reads only from the in-memory ticket store.",
    backed_by="mock (in-memory)",
)

UPDATE_METADATA = ToolMetadata(
    name="update_handoff_ticket",
    description="Update a handoff ticket's summary, reason, and/or status.",
    input_schema=UpdateHandoffTicketInput.model_json_schema(),
    output_schema=UpdateHandoffTicketOutput.model_json_schema(),
    error_behavior="Raises ToolError(code='not_found') when the ticket does not exist.",
    auth_requirement="none (updates only the in-memory ticket store)",
    ownership_boundary="Writes only to the in-memory ticket store.",
    backed_by="mock (in-memory)",
)

DELETE_METADATA = ToolMetadata(
    name="delete_handoff_ticket",
    description="Delete a handoff ticket by ticket ID.",
    input_schema=DeleteHandoffTicketInput.model_json_schema(),
    output_schema=DeleteHandoffTicketOutput.model_json_schema(),
    error_behavior="Raises ToolError(code='not_found') when the ticket does not exist.",
    auth_requirement="none (deletes only from the in-memory ticket store)",
    ownership_boundary="Writes only to the in-memory ticket store.",
    backed_by="mock (in-memory)",
)

_lock = threading.Lock()
_counter = itertools.count(1)
_tickets: list[dict] = []


def _serialize_ticket(record: dict) -> HandoffTicketRecord:
    return HandoffTicketRecord(**record)


def _find_ticket_index(ticket_id: str) -> int:
    for index, record in enumerate(_tickets):
        if record["ticket_id"] == ticket_id:
            return index
    raise ToolError("not_found", f"No handoff ticket found for ticket_id={ticket_id}")


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
            summary=record["summary"],
            reason=record["reason"],
            status=record["status"],
            created_at=record["created_at"],
        )


def get_handoff_ticket(
    conversation_id: str, params: GetHandoffTicketInput
) -> GetHandoffTicketOutput:
    with logged_tool_call("get_handoff_ticket", conversation_id):
        with _lock:
            index = _find_ticket_index(params.ticket_id)
            record = dict(_tickets[index])
        return GetHandoffTicketOutput(**record)


def list_handoff_tickets(
    conversation_id: str, params: ListHandoffTicketsInput
) -> ListHandoffTicketsOutput:
    with logged_tool_call("list_handoff_tickets", conversation_id):
        with _lock:
            records = [
                _serialize_ticket(record)
                for record in _tickets
                if params.status is None or record["status"] == params.status
            ]
        return ListHandoffTicketsOutput(tickets=records[: params.limit])


def update_handoff_ticket(
    conversation_id: str, params: UpdateHandoffTicketInput
) -> UpdateHandoffTicketOutput:
    with logged_tool_call("update_handoff_ticket", conversation_id):
        with _lock:
            index = _find_ticket_index(params.ticket_id)
            record = _tickets[index]
            if params.summary is not None:
                record["summary"] = params.summary
            if params.reason is not None:
                record["reason"] = params.reason
            if params.status is not None:
                record["status"] = params.status
            updated = dict(record)
        return UpdateHandoffTicketOutput(**updated)


def delete_handoff_ticket(
    conversation_id: str, params: DeleteHandoffTicketInput
) -> DeleteHandoffTicketOutput:
    with logged_tool_call("delete_handoff_ticket", conversation_id):
        with _lock:
            index = _find_ticket_index(params.ticket_id)
            deleted_ticket = _tickets.pop(index)
        return DeleteHandoffTicketOutput(ticket_id=deleted_ticket["ticket_id"], deleted=True)


def list_tickets() -> list[dict]:
    """Test/debug helper to inspect tickets created during a process lifetime."""
    with _lock:
        return list(_tickets)
