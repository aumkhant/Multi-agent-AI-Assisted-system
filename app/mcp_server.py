"""Local MCP server exposing this app's tools (catalog, KB, subscription, rental
history, handoff) so an MCP client (e.g. Claude Desktop/Code) can call them directly,
independent of the FastAPI orchestrator. Each tool below is a thin wrapper around the
same functions used by the agents in app/tools/ - same DB queries, same ToolMetadata
contracts, just a different entry point.

Run with: python -m app.mcp_server
"""

from mcp.server.fastmcp import FastMCP

from app.db import get_session
from app.schemas import (
    CreateHandoffTicketInput,
    GetCustomerRentalHistoryInput,
    GetCustomerStreamingSubscriptionInput,
    SearchFilmCatalogInput,
    SearchKbInput,
)
from app.tools.catalog import METADATA as CATALOG_METADATA
from app.tools.catalog import search_film_catalog
from app.tools.handoff import METADATA as HANDOFF_METADATA
from app.tools.handoff import create_handoff_ticket
from app.tools.knowledge_base import METADATA as KB_METADATA
from app.tools.knowledge_base import search_kb
from app.tools.rental_history import METADATA as RENTAL_HISTORY_METADATA
from app.tools.rental_history import get_customer_rental_history
from app.tools.subscription import METADATA as SUBSCRIPTION_METADATA
from app.tools.subscription import get_customer_streaming_subscription

_CONVERSATION_ID = "mcp-server"

mcp = FastMCP(
    "support-assistant-tools",
    instructions="Read/lookup tools for a streaming and rental support assistant "
    "(Pagila-backed film catalog, knowledge base, subscriptions, rental history, and "
    "human handoff tickets).",
)


@mcp.tool(name=CATALOG_METADATA.name, description=CATALOG_METADATA.description)
def search_catalog(query: str) -> dict:
    session = get_session()
    try:
        result = search_film_catalog(session, _CONVERSATION_ID, SearchFilmCatalogInput(query=query))
    finally:
        session.close()
    return result.model_dump()


@mcp.tool(name=SUBSCRIPTION_METADATA.name, description=SUBSCRIPTION_METADATA.description)
def get_streaming_subscription(customer_id: int) -> dict:
    session = get_session()
    try:
        result = get_customer_streaming_subscription(
            session, _CONVERSATION_ID, GetCustomerStreamingSubscriptionInput(customer_id=customer_id)
        )
    finally:
        session.close()
    return result.model_dump()


@mcp.tool(name=RENTAL_HISTORY_METADATA.name, description=RENTAL_HISTORY_METADATA.description)
def get_rental_history(customer_id: int, limit: int = 5) -> dict:
    session = get_session()
    try:
        result = get_customer_rental_history(
            session, _CONVERSATION_ID, GetCustomerRentalHistoryInput(customer_id=customer_id, limit=limit)
        )
    finally:
        session.close()
    return result.model_dump()


@mcp.tool(name=KB_METADATA.name, description=KB_METADATA.description)
def search_knowledge_base(query: str) -> dict:
    result = search_kb(_CONVERSATION_ID, SearchKbInput(query=query))
    return result.model_dump()


@mcp.tool(name=HANDOFF_METADATA.name, description=HANDOFF_METADATA.description)
def create_ticket(summary: str, reason: str) -> dict:
    result = create_handoff_ticket(_CONVERSATION_ID, CreateHandoffTicketInput(summary=summary, reason=reason))
    return result.model_dump()


if __name__ == "__main__":
    mcp.run(transport="stdio")
