import re

_INJECTION_PATTERNS = [
    r"ignore (all|any|previous|prior) instructions",
    r"disregard (all|any|previous|prior) instructions",
    r"reveal (your|the) system prompt",
    r"show (me )?(your|the) (system prompt|instructions|prompt)",
    r"what (are|is) your (system prompt|instructions)",
    r"you are now",
    r"act as (if )?(you|a)",
    r"jailbreak",
    r"developer mode",
]

_MUTATION_PATTERNS = [
    r"cancel (my )?subscription",
    r"cancel (my )?(account|plan)",
    r"delete (my )?account",
    r"close (my )?account",
    r"refund (me|my)",
    r"change (my )?(password|email|payment)",
    r"charge (me|my card)",
    r"downgrade (my )?(plan|subscription)",
    r"upgrade (my )?(plan|subscription)",
]

_HARM_PATTERNS = [
    r"how (do|can|to) i (harm|hurt|attack|kill|poison|assault)",
    r"how to (harm|hurt|attack|kill|poison|assault) (a |an |my |someone|somebody|myself|him|her|them)",
    r"(hurt|harm|kill|attack) (myself|someone|somebody|a person|people)",
    r"(kill|hurt|harm) myself",
    r"(commit|planning) suicide",
    r"(make|build) a (bomb|weapon|explosive|grenade|gun|knife|poison)",
]

_injection_re = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)
_mutation_re = re.compile("|".join(_MUTATION_PATTERNS), re.IGNORECASE)
_harm_re = re.compile("|".join(_HARM_PATTERNS), re.IGNORECASE)


def is_prompt_injection(message: str) -> bool:
    return bool(_injection_re.search(message))


def is_sensitive_mutation_request(message: str) -> bool:
    """A request to change account/billing state, which this assistant must never perform
    directly - it can only escalate/create a handoff ticket."""
    return bool(_mutation_re.search(message))


def is_harmful_content_request(message: str) -> bool:
    """A request seeking help harming a person (self or others) - must be blocked before
    it ever reaches an LLM or gets routed to a specialist agent."""
    return bool(_harm_re.search(message))


def leaks_system_prompt(answer: str) -> bool:
    lowered = answer.lower()
    markers = ["you are a helpful", "system prompt:", "as an ai language model configured"]
    return any(marker in lowered for marker in markers)
