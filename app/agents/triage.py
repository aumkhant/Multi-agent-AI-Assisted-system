import json
import logging
import re
from dataclasses import dataclass

from semantic_kernel import Kernel

from app.agents.llm import complete_chat
from app.schemas import AgentName, Intent

logger = logging.getLogger("triage")

_SYSTEM_PROMPT = """You are the TriageAgent for a streaming/rental support assistant.
Classify the customer's message into exactly one intent and choose the specialist agent
to handle it. Respond with ONLY a JSON object, no prose, matching this shape:
{"intent": "<intent>", "selected_agent": "<agent>", "confidence": <0.0-1.0>, "reason": "<short reason>"}

Valid (intent, selected_agent) pairs:
- ("catalog_search", "CatalogAgent") - questions about whether a film is available, streamable, its rating/rental rate/category.
- ("subscription_question", "SubscriptionAgent") - questions about subscription status, plan, renewal, auto-renew.
- ("rental_history", "RentalHistoryAgent") - questions about what the customer has rented recently.
- ("knowledge_question", "KnowledgeAgent") - general how-do-I support questions (payment method, account settings, troubleshooting).
- ("human_handoff", "HumanHandoffAgent") - explicit requests to talk to a human, or anything you are unsure how to classify.

If you are not confident, still return your best guess but set a low confidence score.
"""

_INTENT_AGENT: dict[Intent, AgentName] = {
    "catalog_search": "CatalogAgent",
    "subscription_question": "SubscriptionAgent",
    "rental_history": "RentalHistoryAgent",
    "knowledge_question": "KnowledgeAgent",
    "human_handoff": "HumanHandoffAgent",
}

_KEYWORD_RULES: list[tuple[re.Pattern, Intent]] = [
    (re.compile(r"stream|available|watch|rating|rental rate|category", re.I), "catalog_search"),
    (re.compile(r"subscription|plan|renew|auto-renew|auto renew", re.I), "subscription_question"),
    (re.compile(r"rent(ed|al)?.*(history|recent)|what.*rented|watched recently", re.I), "rental_history"),
    (re.compile(r"payment|password|account setting|how do i|troubleshoot", re.I), "knowledge_question"),
    (re.compile(r"human|agent|representative|talk to (a )?person", re.I), "human_handoff"),
]


@dataclass
class TriageResult:
    intent: Intent
    selected_agent: AgentName
    confidence: float
    reason: str


def _deterministic_fallback(message: str) -> TriageResult:
    for pattern, intent in _KEYWORD_RULES:
        if pattern.search(message):
            return TriageResult(
                intent=intent,
                selected_agent=_INTENT_AGENT[intent],
                confidence=0.4,
                reason="Deterministic keyword fallback (LLM triage unavailable or unparsable).",
            )
    return TriageResult(
        intent="human_handoff",
        selected_agent="HumanHandoffAgent",
        confidence=0.2,
        reason="No keyword match; escalating to a human as a safe default.",
    )


def _parse_llm_response(raw: str) -> TriageResult | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        intent = data["intent"]
        selected_agent = data["selected_agent"]
        confidence = float(data["confidence"])
        reason = str(data.get("reason", ""))
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
    if intent not in _INTENT_AGENT or _INTENT_AGENT[intent] != selected_agent:
        return None
    return TriageResult(intent=intent, selected_agent=selected_agent, confidence=confidence, reason=reason)


async def classify(kernel: Kernel, message: str) -> TriageResult:
    try:
        raw = await complete_chat(kernel, _SYSTEM_PROMPT, message, temperature=0.0)
    except Exception:
        logger.exception("triage_llm_call_failed")
        return _deterministic_fallback(message)

    parsed = _parse_llm_response(raw)
    if parsed is None:
        logger.warning("triage_llm_response_unparsable", extra={"raw": raw})
        return _deterministic_fallback(message)
    return parsed
