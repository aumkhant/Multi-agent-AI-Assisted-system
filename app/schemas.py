from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal[
    "catalog_search",
    "subscription_question",
    "rental_history",
    "knowledge_question",
    "human_handoff",
    "unsafe_request",
]

AgentName = Literal[
    "TriageAgent",
    "CatalogAgent",
    "SubscriptionAgent",
    "RentalHistoryAgent",
    "KnowledgeAgent",
    "HumanHandoffAgent",
    "GuardrailAgent",
]

NextAction = Literal[
    "none",
    "await_customer_id",
    "handoff_created",
    "escalate_to_human",
]

GuardrailResult = Literal["pass", "modified", "blocked"]


class AgentRequest(BaseModel):
    customer_id: int | None = None
    conversation_id: str
    message: str


class AgentResponse(BaseModel):
    conversation_id: str
    intent: Intent
    selected_agent: AgentName
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    tools_used: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    next_action: NextAction
    guardrail_result: GuardrailResult
