import logging

from openai import AsyncOpenAI

from app.utils.tracing import trace_operation
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import (
    OpenAIChatCompletion,
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.contents.chat_history import ChatHistory

from app.config import settings

logger = logging.getLogger("llm")

_SERVICE_ID = "chat"


def build_kernel() -> Kernel:
    kernel = Kernel()
    if settings.openai_base_url:
        # Points at an OpenAI-compatible endpoint (e.g. local Ollama) instead of
        # the real OpenAI API - used when no funded OpenAI key is available.
        async_client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key or "not-needed",
        )
        chat_service = OpenAIChatCompletion(
            ai_model_id=settings.openai_model,
            async_client=async_client,
            service_id=_SERVICE_ID,
        )
    else:
        chat_service = OpenAIChatCompletion(
            ai_model_id=settings.openai_model,
            api_key=settings.openai_api_key,
            service_id=_SERVICE_ID,
        )
    kernel.add_service(chat_service)
    return kernel


def _extract_usage_metadata(result: object) -> dict[str, int | str]:
    metadata: dict[str, int | str] = {}
    usage = getattr(result, "usage", None)
    if usage is None:
        return metadata

    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)

    if input_tokens is not None:
        metadata["gen_ai.usage.input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        metadata["gen_ai.usage.output_tokens"] = int(output_tokens)
    if total_tokens is not None:
        metadata["gen_ai.usage.total_tokens"] = int(total_tokens)

    return metadata


async def complete_chat(
    kernel: Kernel, system_prompt: str, user_prompt: str, temperature: float = 0.2
) -> str:
    """Runs one system+user turn through the kernel's chat completion service and returns text."""
    service = kernel.get_service(_SERVICE_ID)
    history = ChatHistory()
    history.add_system_message(system_prompt)
    history.add_user_message(user_prompt)
    exec_settings = OpenAIChatPromptExecutionSettings(temperature=temperature)
    with trace_operation(
        "llm.complete_chat",
        {"service_id": _SERVICE_ID, "model": settings.openai_model, "temperature": temperature},
    ) as span:
        result = await service.get_chat_message_content(chat_history=history, settings=exec_settings)
        response_text = str(result)
        usage_metadata = _extract_usage_metadata(result)
        usage_metadata["llm.model"] = settings.openai_model
        for key, value in usage_metadata.items():
            if isinstance(value, (str, bool, int, float)):
                span.set_attribute(key, value)
            else:
                span.set_attribute(key, str(value))
    return response_text
