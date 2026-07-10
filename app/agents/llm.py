import logging

from openai import AsyncOpenAI
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


async def complete_chat(kernel: Kernel, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    """Runs one system+user turn through the kernel's chat completion service and returns text."""
    service = kernel.get_service(_SERVICE_ID)
    history = ChatHistory()
    history.add_system_message(system_prompt)
    history.add_user_message(user_prompt)
    exec_settings = OpenAIChatPromptExecutionSettings(temperature=temperature)
    result = await service.get_chat_message_content(chat_history=history, settings=exec_settings)
    return str(result)
