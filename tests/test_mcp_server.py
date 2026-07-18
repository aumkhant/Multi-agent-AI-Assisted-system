import pytest

from app.mcp_server import mcp


@pytest.mark.asyncio
async def test_all_tools_are_registered_with_names_matching_tool_metadata():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert names == {
        "search_film_catalog",
        "get_customer_streaming_subscription",
        "get_customer_rental_history",
        "search_kb",
        "create_handoff_ticket",
        "get_handoff_ticket",
        "list_handoff_tickets",
        "update_handoff_ticket",
        "delete_handoff_ticket",
        "search_web",
    }


@pytest.mark.asyncio
async def test_search_catalog_tool_input_schema_matches_query_param():
    tools = await mcp.list_tools()
    catalog_tool = next(tool for tool in tools if tool.name == "search_film_catalog")
    assert catalog_tool.inputSchema["required"] == ["query"]
