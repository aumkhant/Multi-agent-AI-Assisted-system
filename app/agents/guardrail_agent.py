from app.guardrails.checks import leaks_system_prompt
from app.schemas import GuardrailResult, Intent

_GROUNDED_INTENTS: set[Intent] = {
    "catalog_search",
    "subscription_question",
    "rental_history",
    "knowledge_question",
}


def review(
    answer: str, intent: Intent, tools_used: list[str], next_action: str
) -> tuple[str, GuardrailResult]:
    """Final safety/schema/wording pass over the answer an agent produced. Returns the
    (possibly rewritten) answer and a guardrail_result of pass/modified/blocked."""

    if leaks_system_prompt(answer):
        return (
            "I can't share internal system instructions, but I'm happy to help with your "
            "support question.",
            "blocked",
        )

    if intent in _GROUNDED_INTENTS and not tools_used and next_action == "none":
        return (
            "I don't have enough verified information to answer that confidently. Let me "
            "connect you with a human agent instead.",
            "blocked",
        )

    if not answer.strip():
        return ("Sorry, I wasn't able to generate a response. Let me escalate this to a human agent.", "modified")
    
    return (answer, "pass")
