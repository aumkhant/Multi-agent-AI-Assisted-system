from typing import TypeVar

from pydantic import BaseModel

from app.mcp_tools import dispatch_tool_call

ModelT = TypeVar("ModelT", bound=BaseModel)


async def call_tool(
    tool_name: str,
    conversation_id: str,
    arguments: dict,
    output_model: type[ModelT],
) -> ModelT:
    payload = dispatch_tool_call(tool_name, conversation_id, arguments)
    return output_model.model_validate(payload)
