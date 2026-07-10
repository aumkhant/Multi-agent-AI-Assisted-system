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
)
from app.config import settings
from app.db import get_session
from app.guardrails.checks import (
    is_harmful_content_request,
    is_prompt_injection,
    is_sensitive_mutation_request,
)
from app.schemas import AgentResponse

logger = logging.getLogger("orchestrator")


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
        outcome = handoff_agent.handle(conversation_id, message, reason="sensitive_account_mutation_request")
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

    triage_result = await triage.classify(kernel, message)

    if (
        triage_result.confidence < settings.triage_confidence_threshold
        and triage_result.selected_agent != "HumanHandoffAgent"
    ):
        outcome = handoff_agent.handle(
            conversation_id, message, reason=f"low_confidence_routing: {triage_result.reason}"
        )
        answer, guardrail_result = guardrail_agent.review(
            outcome.answer, "human_handoff", outcome.tools_used, outcome.next_action
        )
        return AgentResponse(
            conversation_id=conversation_id,
            intent="human_handoff",
            selected_agent="HumanHandoffAgent",
            answer=answer,
            confidence=triage_result.confidence,
            tools_used=outcome.tools_used,
            citations=outcome.citations,
            next_action=outcome.next_action,
            guardrail_result=guardrail_result,
        )

    session = get_session()
    try:
        if triage_result.selected_agent == "CatalogAgent":
            outcome = await catalog_agent.handle(kernel, session, conversation_id, message)
        elif triage_result.selected_agent == "SubscriptionAgent":
            outcome = await subscription_agent.handle(kernel, session, conversation_id, message, customer_id)
        elif triage_result.selected_agent == "RentalHistoryAgent":
            outcome = await rental_history_agent.handle(kernel, session, conversation_id, message, customer_id)
        elif triage_result.selected_agent == "KnowledgeAgent":
            outcome = await knowledge_agent.handle(kernel, conversation_id, message)
        else:
            outcome = handoff_agent.handle(conversation_id, message, reason="explicit_human_handoff_request")
    finally:
        session.close()

    answer, guardrail_result = guardrail_agent.review(
        outcome.answer, triage_result.intent, outcome.tools_used, outcome.next_action
    )

    return AgentResponse(
        conversation_id=conversation_id,
        intent=triage_result.intent,
        selected_agent=triage_result.selected_agent,
        answer=answer,
        confidence=triage_result.confidence,
        tools_used=outcome.tools_used,
        citations=outcome.citations,
        next_action=outcome.next_action,
        guardrail_result=guardrail_result,
    )
