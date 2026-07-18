"""Local MCP server exposing this app's tools over a shared registry."""

from dataclasses import dataclass
from typing import Any

from app.mcp_tools import dispatch_tool_call

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    @dataclass
    class _ToolInfo:
        name: str
        description: str
        inputSchema: dict[str, Any]


    class FastMCP:  # pragma: no cover - shim used only when the external package is unavailable
        def __init__(self, name: str, instructions: str):
            self.name = name
            self.instructions = instructions
            self._tools: list[_ToolInfo] = []

        def tool(self, name: str, description: str):
            def decorator(func):
                input_schema = getattr(func, "__input_schema__", {"type": "object", "properties": {}, "required": []})
                self._tools.append(_ToolInfo(name=name, description=description, inputSchema=input_schema))
                return func

            return decorator

        async def list_tools(self) -> list[_ToolInfo]:
            return list(self._tools)

        def run(self, transport: str = "stdio") -> None:
            raise RuntimeError("The mcp package is not installed, so the local MCP server cannot run.")


def _attach_schema(schema: dict[str, Any]):
    def decorator(func):
        func.__input_schema__ = schema
        return func

    return decorator


mcp = FastMCP(
    "support-assistant-tools",
    instructions="Read/lookup tools for a streaming and rental support assistant "
    "(Pagila-backed film catalog, knowledge base, subscriptions, rental history, handoff "
    "ticket CRUD, and public web search fallback).",
)


@mcp.tool(name="search_film_catalog", description="Search the film catalog by title and return category, rating, rental rate, and streaming availability.")
@_attach_schema(
    {
        "type": "object",
        "properties": {"query": {"title": "Query", "type": "string"}},
        "required": ["query"],
    }
)
def search_catalog(query: str) -> dict:
    return dispatch_tool_call("search_film_catalog", "mcp-server", {"query": query})


@mcp.tool(name="get_customer_streaming_subscription", description="Look up a customer's streaming subscription status, plan, renewal date, and auto-renew flag.")
@_attach_schema(
    {
        "type": "object",
        "properties": {"customer_id": {"title": "Customer Id", "type": "integer"}},
        "required": ["customer_id"],
    }
)
def get_streaming_subscription(customer_id: int) -> dict:
    return dispatch_tool_call("get_customer_streaming_subscription", "mcp-server", {"customer_id": customer_id})


@mcp.tool(name="get_customer_rental_history", description="Return a customer's most recent rentals (film title, rental date, return date).")
@_attach_schema(
    {
        "type": "object",
        "properties": {
            "customer_id": {"title": "Customer Id", "type": "integer"},
            "limit": {"title": "Limit", "type": "integer", "default": 5},
        },
        "required": ["customer_id"],
    }
)
def get_rental_history(customer_id: int, limit: int = 5) -> dict:
    return dispatch_tool_call(
        "get_customer_rental_history",
        "mcp-server",
        {"customer_id": customer_id, "limit": limit},
    )


@mcp.tool(name="search_kb", description="Search local knowledge base articles for support topics and return matching articles with source references.")
@_attach_schema(
    {
        "type": "object",
        "properties": {"query": {"title": "Query", "type": "string"}},
        "required": ["query"],
    }
)
def search_knowledge_base(query: str) -> dict:
    return dispatch_tool_call("search_kb", "mcp-server", {"query": query})


@mcp.tool(name="create_handoff_ticket", description="Simulate creating an escalation ticket for a human support agent. Does not perform any account mutation.")
@_attach_schema(
    {
        "type": "object",
        "properties": {
            "summary": {"title": "Summary", "type": "string"},
            "reason": {"title": "Reason", "type": "string"},
        },
        "required": ["summary", "reason"],
    }
)
def create_ticket(summary: str, reason: str) -> dict:
    return dispatch_tool_call("create_handoff_ticket", "mcp-server", {"summary": summary, "reason": reason})


@mcp.tool(name="get_handoff_ticket", description="Get a single human handoff ticket by ticket ID.")
@_attach_schema(
    {
        "type": "object",
        "properties": {"ticket_id": {"title": "Ticket Id", "type": "string"}},
        "required": ["ticket_id"],
    }
)
def get_ticket(ticket_id: str) -> dict:
    return dispatch_tool_call("get_handoff_ticket", "mcp-server", {"ticket_id": ticket_id})


@mcp.tool(name="list_handoff_tickets", description="List handoff tickets, optionally filtered by status.")
@_attach_schema(
    {
        "type": "object",
        "properties": {
            "status": {"title": "Status", "type": "string"},
            "limit": {"title": "Limit", "type": "integer", "default": 20},
        },
        "required": [],
    }
)
def list_ticket_records(status: str | None = None, limit: int = 20) -> dict:
    payload: dict[str, Any] = {"limit": limit}
    if status is not None:
        payload["status"] = status
    return dispatch_tool_call("list_handoff_tickets", "mcp-server", payload)


@mcp.tool(name="update_handoff_ticket", description="Update a handoff ticket's summary, reason, and/or status.")
@_attach_schema(
    {
        "type": "object",
        "properties": {
            "ticket_id": {"title": "Ticket Id", "type": "string"},
            "summary": {"title": "Summary", "type": "string"},
            "reason": {"title": "Reason", "type": "string"},
            "status": {"title": "Status", "type": "string"},
        },
        "required": ["ticket_id"],
    }
)
def update_ticket(
    ticket_id: str,
    summary: str | None = None,
    reason: str | None = None,
    status: str | None = None,
) -> dict:
    payload: dict[str, Any] = {"ticket_id": ticket_id}
    if summary is not None:
        payload["summary"] = summary
    if reason is not None:
        payload["reason"] = reason
    if status is not None:
        payload["status"] = status
    return dispatch_tool_call("update_handoff_ticket", "mcp-server", payload)


@mcp.tool(name="delete_handoff_ticket", description="Delete a handoff ticket by ticket ID.")
@_attach_schema(
    {
        "type": "object",
        "properties": {"ticket_id": {"title": "Ticket Id", "type": "string"}},
        "required": ["ticket_id"],
    }
)
def delete_ticket(ticket_id: str) -> dict:
    return dispatch_tool_call("delete_handoff_ticket", "mcp-server", {"ticket_id": ticket_id})


@mcp.tool(name="search_web", description="Search the public web for a query and return short snippets with source URLs.")
@_attach_schema(
    {
        "type": "object",
        "properties": {"query": {"title": "Query", "type": "string"}},
        "required": ["query"],
    }
)
def search_public_web(query: str) -> dict:
    return dispatch_tool_call("search_web", "mcp-server", {"query": query})


if __name__ == "__main__":
    mcp.run(transport="stdio")
