import re

_STOPWORDS = {
    "is",
    "are",
    "the",
    "a",
    "an",
    "available",
    "for",
    "streaming",
    "stream",
    "movie",
    "film",
    "on",
    "in",
    "to",
    "watch",
    "can",
    "i",
    "my",
    "does",
    "do",
    "we",
    "have",
    "has",
}


def extract_title_query(message: str) -> str:
    """Best-effort extraction of a likely film title from a natural-language question."""
    words = re.findall(r"[A-Za-z0-9']+", message)
    filtered = [w for w in words if w.lower() not in _STOPWORDS]
    return " ".join(filtered) if filtered else message.strip()
