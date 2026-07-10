from dataclasses import dataclass, field

from app.schemas import NextAction


@dataclass
class AgentOutcome:
    answer: str
    tools_used: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    next_action: NextAction = "none"
