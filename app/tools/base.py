import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("tools")


class ToolError(Exception):
    """Raised by a tool when it cannot fulfil the request (not found, bad input, etc.)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ToolMetadata:
    """MCP-ready description of a tool's contract, independent of how it's invoked."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    error_behavior: str
    auth_requirement: str
    ownership_boundary: str
    backed_by: str = field(default="unspecified")


@contextmanager
def logged_tool_call(tool_name: str, conversation_id: str):
    """Logs a structured record for every tool invocation: id, name, status, latency, error."""
    start = time.monotonic()
    status = "ok"
    error_detail: str | None = None
    try:
        yield
    except ToolError as exc:
        status = "error"
        error_detail = f"{exc.code}: {exc.message}"
        raise
    except Exception as exc:  # noqa: BLE001 - log unexpected errors then re-raise
        status = "error"
        error_detail = f"unexpected: {exc}"
        raise
    finally:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "tool_call",
            extra={
                "conversation_id": conversation_id,
                "tool_name": tool_name,
                "status": status,
                "latency_ms": latency_ms,
                "error": error_detail,
            },
        )
