import logging

from semantic_kernel import Kernel

from app.agents import (
    catalog_agent,
    guardrail_agent,
    handoff_agent,
    knowledge_agent,
    rental_history_agent,
    subscription_agent,
    triage,
    web_search_agent,
)
from app.guardrails.checks import (
    is_harmful_content_request,
    is_prompt_injection,
    is_sensitive_mutation_request,
)
from app.schemas import AgentResponse
from app.utils.llm import complete_chat

logger = logging.getLogger("orchestrator")

GUARDRAIL_CHECK_PROMPT = '''
You are a safety and privacy guardrail for a streaming and rental support assistant.
Classify the user's message as either "safe" or "unsafe".

Mark the request as "unsafe" only if it does one of these:
1. Asks for another person's account, billing, rental, subscription, or personal information.
2. Asks to access, reveal, or change another person's account details.
3. Clearly requests disallowed harmful assistance.

Mark the request as "safe" for ordinary support and catalog questions, including:
- movie or streaming availability
- where to watch a title
- subscription status for the requesting user
- rental history for the requesting user
- troubleshooting or knowledge-base questions
- requests to update the requesting user's own account details

Important:
- A movie title, franchise, or word like "Alien" is not harmful by itself.
- Do not mark a request unsafe just because it mentions a film title, streaming, or watching something.
- If the request is a normal first-party customer support request and does not ask about another person's account, return "safe".

Respond with exactly one word: "safe" or "unsafe".
'''


async def handle_request(kernel: Kernel, conversation_id: str, message: str, customer_id: int | None) -> AgentResponse:
    # Deterministic safety checks run before any LLM call - they must not be bypassable
    # by prompt content, and must not depend on the LLM behaving correctly.
    if is_prompt_injection(message):
        logger.info("guardrail_blocked_prompt_injection", extra={"conversation_id": conversation_id})
        return AgentResponse(
            conversation_id=conversation_id,
            intent="unsafe_request",
            selected_agent="GuardrailAgent",
            answer="I can't share internal system instructions or configuration, but I'm "
            "happy to help with a support question.",
            confidence=1.0,
            tools_used=[],
            citations=[],
            next_action="none",
            guardrail_result="blocked",
        )

    if is_harmful_content_request(message):
        logger.info("guardrail_blocked_harmful_content", extra={"conversation_id": conversation_id})
        return AgentResponse(
            conversation_id=conversation_id,
            intent="unsafe_request",
            selected_agent="GuardrailAgent",
            answer="I can't help with that. If you or someone else is in danger, please "
            "contact local emergency services or a crisis helpline right away.",
            confidence=1.0,
            tools_used=[],
            citations=[],
            next_action="none",
            guardrail_result="blocked",
        )

    if is_sensitive_mutation_request(message):
        outcome = await handoff_agent.handle(
            conversation_id, message, reason="sensitive_account_mutation_request"
        )
        logger.info("guardrail_escalated_mutation_request", extra={"conversation_id": conversation_id})
        return AgentResponse(
            conversation_id=conversation_id,
            intent="human_handoff",
            selected_agent="HumanHandoffAgent",
            answer=outcome.answer,
            confidence=1.0,
            tools_used=outcome.tools_used,
            citations=outcome.citations,
            next_action=outcome.next_action,
            guardrail_result="modified",
        )

    guardrail_llm_check = await complete_chat(kernel, GUARDRAIL_CHECK_PROMPT, message, temperature=0.0)
    if guardrail_llm_check.strip().lower() == "unsafe":
        logger.info("guardrail_blocked_llm_check", extra={"conversation_id": conversation_id})
        return AgentResponse(
            conversation_id=conversation_id,
            intent="unsafe_request",
            selected_agent="GuardrailAgent",
            answer="I can't help with that. If you or someone else is in danger, please "
            "contact local emergency services or a crisis helpline right away.",
            confidence=1.0,
            tools_used=[],
            citations=[],
            next_action="none",
            guardrail_result="blocked",
        )

    triage_result = await triage.classify(kernel, message)

    if triage_result.intent == "out_of_scope":
        answer, guardrail_result = guardrail_agent.review(
            "I can help only with this streaming and rental support service, such as film "
            "availability, subscriptions, rental history, and account help. I can't answer "
            "general world-knowledge or unrelated-topic questions.",
            "out_of_scope",
            [],
            "none",
        )
        return AgentResponse(
            conversation_id=conversation_id,
            intent="out_of_scope",
            selected_agent="GuardrailAgent",
            answer=answer,
            confidence=triage_result.confidence,
            tools_used=[],
            citations=[],
            next_action="none",
            guardrail_result=guardrail_result,
        )
    
    if triage_result.selected_agent == "CatalogAgent":
        outcome = await catalog_agent.handle(kernel, conversation_id, message)
    elif triage_result.selected_agent == "SubscriptionAgent":
        outcome = await subscription_agent.handle(kernel, conversation_id, message, customer_id)
    elif triage_result.selected_agent == "RentalHistoryAgent":
        outcome = await rental_history_agent.handle(kernel, conversation_id, message, customer_id)
    elif triage_result.selected_agent == "KnowledgeAgent":
        outcome = await knowledge_agent.handle(kernel, conversation_id, message)
    elif triage_result.selected_agent == "HumanHandoffAgent":
        outcome = await handoff_agent.handle(conversation_id, message, reason="explicit_human_handoff_request")
    else:
        raise ValueError(f"Unsupported selected agent: {triage_result.selected_agent}")

    selected_agent = triage_result.selected_agent
    if not outcome.answered and triage_result.selected_agent not in {"HumanHandoffAgent", "GuardrailAgent"}:
        specialist_tools = outcome.tools_used
        web_outcome = await web_search_agent.handle(kernel, conversation_id, message)
        # A specialist miss must be answered by the web-fallback path, even when the
        # public provider has no result. Never return the original specialist miss.
        web_outcome.tools_used = [*specialist_tools, *web_outcome.tools_used]
        outcome = web_outcome
        selected_agent = "WebSearchAgent"

    answer, guardrail_result = guardrail_agent.review(
        outcome.answer, triage_result.intent, outcome.tools_used, outcome.next_action
    )

    return AgentResponse(
        conversation_id=conversation_id,
        intent=triage_result.intent,
        selected_agent=selected_agent,
        answer=answer,
        confidence=triage_result.confidence,
        tools_used=outcome.tools_used,
        citations=outcome.citations,
        next_action=outcome.next_action,
        guardrail_result=guardrail_result,
    )
