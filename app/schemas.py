from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal[
    "catalog_search",
    "subscription_question",
    "rental_history",
    "knowledge_question",
    "human_handoff",
    "out_of_scope",
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


class FilmResult(BaseModel):
    title: str
    category: str
    rating: str
    rental_rate: float
    streaming_available: bool


class SearchFilmCatalogInput(BaseModel):
    query: str


class SearchFilmCatalogOutput(BaseModel):
    results: list[FilmResult]


class GetCustomerStreamingSubscriptionInput(BaseModel):
    customer_id: int


class GetCustomerStreamingSubscriptionOutput(BaseModel):
    plan_name: str
    status: str
    start_date: date
    end_date: date | None
    auto_renew: bool


class RentalRecord(BaseModel):
    title: str
    rental_date: datetime
    return_date: datetime | None


class GetCustomerRentalHistoryInput(BaseModel):
    customer_id: int
    limit: int = 5


class GetCustomerRentalHistoryOutput(BaseModel):
    rentals: list[RentalRecord]


class KbArticle(BaseModel):
    title: str
    snippet: str
    source: str


class SearchKbInput(BaseModel):
    query: str


class SearchKbOutput(BaseModel):
    articles: list[KbArticle]


class CreateHandoffTicketInput(BaseModel):
    summary: str
    reason: str


class CreateHandoffTicketOutput(BaseModel):
    ticket_id: str
    status: str
    created_at: datetime
