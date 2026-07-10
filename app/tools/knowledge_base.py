import re
from pathlib import Path

from pydantic import BaseModel

from app.tools.base import ToolMetadata, logged_tool_call

KB_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge_base"


class SearchKbInput(BaseModel):
    query: str


class KbArticle(BaseModel):
    title: str
    snippet: str
    source: str


class SearchKbOutput(BaseModel):
    articles: list[KbArticle]


METADATA = ToolMetadata(
    name="search_kb",
    description="Search local knowledge base articles for support topics and return "
    "matching articles with source references.",
    input_schema=SearchKbInput.model_json_schema(),
    output_schema=SearchKbOutput.model_json_schema(),
    error_behavior="Returns an empty articles list when no article matches; never raises.",
    auth_requirement="none (general support content, no customer data)",
    ownership_boundary="Reads only local files under knowledge_base/; no writes, no DB access.",
    backed_by="local files",
)


def _load_articles() -> list[tuple[str, str, str]]:
    articles = []
    for path in sorted(KB_DIR.glob("*.md")):
        text = path.read_text()
        title = text.splitlines()[0].lstrip("# ").strip()
        articles.append((title, text, path.name))
    return articles


def _score(query_terms: set[str], text: str) -> int:
    text_lower = text.lower()
    return sum(1 for term in query_terms if term in text_lower)


def search_kb(conversation_id: str, params: SearchKbInput) -> SearchKbOutput:
    with logged_tool_call("search_kb", conversation_id):
        query_terms = {t for t in re.findall(r"[a-z0-9]+", params.query.lower()) if len(t) > 2}
        scored = []
        for title, text, source in _load_articles():
            score = _score(query_terms, text)
            if score > 0:
                scored.append((score, title, text, source))
        scored.sort(key=lambda item: item[0], reverse=True)
        articles = [
            KbArticle(title=title, snippet=" ".join(text.split()[:40]) + "...", source=source)
            for _, title, text, source in scored[:3]
        ]
        return SearchKbOutput(articles=articles)
