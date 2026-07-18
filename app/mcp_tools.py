from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.db import get_session
from app.schemas import (
    CreateHandoffTicketInput,
    DeleteHandoffTicketInput,
    GetCustomerRentalHistoryInput,
    GetCustomerStreamingSubscriptionInput,
    GetHandoffTicketInput,
    ListHandoffTicketsInput,
    SearchFilmCatalogInput,
    SearchKbInput,
    SearchWebInput,
    UpdateHandoffTicketInput,
)
from app.tools.catalog import METADATA as CATALOG_METADATA
from app.tools.catalog import search_film_catalog
from app.tools.handoff import CREATE_METADATA, DELETE_METADATA, GET_METADATA, LIST_METADATA, UPDATE_METADATA
from app.tools.handoff import (
    create_handoff_ticket,
    delete_handoff_ticket,
    get_handoff_ticket,
    list_handoff_tickets,
    update_handoff_ticket,
)
from app.tools.knowledge_base import METADATA as KB_METADATA
from app.tools.knowledge_base import search_kb
from app.tools.rental_history import METADATA as RENTAL_HISTORY_METADATA
from app.tools.rental_history import get_customer_rental_history
from app.tools.subscription import METADATA as SUBSCRIPTION_METADATA
from app.tools.subscription import get_customer_streaming_subscription
from app.tools.web_search import METADATA as WEB_SEARCH_METADATA
from app.tools.web_search import search_web

McpHandler = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class McpToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: McpHandler


def _with_session(callable_: Callable[[Any, str, Any], Any], conversation_id: str, params: Any) -> dict[str, Any]:
    session = get_session()
    try:
        result = callable_(session, conversation_id, params)
    finally:
        session.close()
    return result.model_dump()


def _catalog_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return _with_session(search_film_catalog, conversation_id, SearchFilmCatalogInput(**arguments))


def _subscription_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return _with_session(
        get_customer_streaming_subscription,
        conversation_id,
        GetCustomerStreamingSubscriptionInput(**arguments),
    )


def _rental_history_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return _with_session(
        get_customer_rental_history,
        conversation_id,
        GetCustomerRentalHistoryInput(**arguments),
    )


def _kb_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return search_kb(conversation_id, SearchKbInput(**arguments)).model_dump()


def _create_handoff_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return create_handoff_ticket(conversation_id, CreateHandoffTicketInput(**arguments)).model_dump()


def _get_handoff_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return get_handoff_ticket(conversation_id, GetHandoffTicketInput(**arguments)).model_dump()


def _list_handoff_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return list_handoff_tickets(conversation_id, ListHandoffTicketsInput(**arguments)).model_dump()


def _update_handoff_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return update_handoff_ticket(conversation_id, UpdateHandoffTicketInput(**arguments)).model_dump()


def _delete_handoff_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return delete_handoff_ticket(conversation_id, DeleteHandoffTicketInput(**arguments)).model_dump()


def _web_search_handler(conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return search_web(conversation_id, SearchWebInput(**arguments)).model_dump()


TOOL_SPECS: dict[str, McpToolSpec] = {
    CATALOG_METADATA.name: McpToolSpec(
        name=CATALOG_METADATA.name,
        description=CATALOG_METADATA.description,
        input_schema=CATALOG_METADATA.input_schema,
        handler=_catalog_handler,
    ),
    SUBSCRIPTION_METADATA.name: McpToolSpec(
        name=SUBSCRIPTION_METADATA.name,
        description=SUBSCRIPTION_METADATA.description,
        input_schema=SUBSCRIPTION_METADATA.input_schema,
        handler=_subscription_handler,
    ),
    RENTAL_HISTORY_METADATA.name: McpToolSpec(
        name=RENTAL_HISTORY_METADATA.name,
        description=RENTAL_HISTORY_METADATA.description,
        input_schema=RENTAL_HISTORY_METADATA.input_schema,
        handler=_rental_history_handler,
    ),
    KB_METADATA.name: McpToolSpec(
        name=KB_METADATA.name,
        description=KB_METADATA.description,
        input_schema=KB_METADATA.input_schema,
        handler=_kb_handler,
    ),
    CREATE_METADATA.name: McpToolSpec(
        name=CREATE_METADATA.name,
        description=CREATE_METADATA.description,
        input_schema=CREATE_METADATA.input_schema,
        handler=_create_handoff_handler,
    ),
    GET_METADATA.name: McpToolSpec(
        name=GET_METADATA.name,
        description=GET_METADATA.description,
        input_schema=GET_METADATA.input_schema,
        handler=_get_handoff_handler,
    ),
    LIST_METADATA.name: McpToolSpec(
        name=LIST_METADATA.name,
        description=LIST_METADATA.description,
        input_schema=LIST_METADATA.input_schema,
        handler=_list_handoff_handler,
    ),
    UPDATE_METADATA.name: McpToolSpec(
        name=UPDATE_METADATA.name,
        description=UPDATE_METADATA.description,
        input_schema=UPDATE_METADATA.input_schema,
        handler=_update_handoff_handler,
    ),
    DELETE_METADATA.name: McpToolSpec(
        name=DELETE_METADATA.name,
        description=DELETE_METADATA.description,
        input_schema=DELETE_METADATA.input_schema,
        handler=_delete_handoff_handler,
    ),
    WEB_SEARCH_METADATA.name: McpToolSpec(
        name=WEB_SEARCH_METADATA.name,
        description=WEB_SEARCH_METADATA.description,
        input_schema=WEB_SEARCH_METADATA.input_schema,
        handler=_web_search_handler,
    ),
}


def list_tool_specs() -> list[McpToolSpec]:
    return list(TOOL_SPECS.values())


def dispatch_tool_call(tool_name: str, conversation_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        spec = TOOL_SPECS[tool_name]
    except KeyError as exc:
        raise ValueError(f"Unknown MCP tool: {tool_name}") from exc
    return spec.handler(conversation_id, arguments)
