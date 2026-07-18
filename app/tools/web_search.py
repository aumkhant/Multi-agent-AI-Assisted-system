import html
import json
import logging
import os
import re
import ssl
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from app.schemas import SearchWebInput, SearchWebOutput, WebSearchResult
from app.tools.base import ToolMetadata, logged_tool_call


logger = logging.getLogger("tools.web_search")


METADATA = ToolMetadata(
    name="search_web",
    description="Search the public web for a query and return short snippets with source URLs.",
    input_schema=SearchWebInput.model_json_schema(),
    output_schema=SearchWebOutput.model_json_schema(),
    error_behavior="Returns an empty results list when no public search results are available.",
    auth_requirement="none (public web search only)",
    ownership_boundary="Reads only public web search results; no writes.",
    backed_by="duckduckgo instant answer api + html search results fallback",
)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_SYSTEM_CA_BUNDLE = Path("/etc/ssl/cert.pem")
_STOPWORDS = {
    "is",
    "are",
    "am",
    "was",
    "were",
    "be",
    "been",
    "being",
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "for",
    "on",
    "in",
    "my",
    "right",
    "now",
    "can",
    "i",
    "watch",
    "where",
}


class _DuckDuckGoHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[WebSearchResult] = []
        self._in_result_link = False
        self._capture_snippet = False
        self._current_href = ""
        self._current_title_parts: list[str] = []
        self._current_snippet_parts: list[str] = []
        self._last_result_index: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class") or ""
        if tag == "a" and "result__a" in classes:
            self._in_result_link = True
            self._current_href = attrs_dict.get("href") or ""
            self._current_title_parts = []
            self._current_snippet_parts = []
        elif tag in {"a", "div"} and ("result__snippet" in classes or "result-snippet" in classes):
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            title = _clean_text("".join(self._current_title_parts))
            url = _extract_duckduckgo_target(self._current_href)
            if title and url:
                self.results.append(WebSearchResult(title=title, snippet="", url=url))
                self._last_result_index = len(self.results) - 1
            self._in_result_link = False
            self._current_href = ""
            self._current_title_parts = []
        elif tag in {"a", "div"} and self._capture_snippet:
            snippet = _clean_text("".join(self._current_snippet_parts))
            if snippet and self._last_result_index is not None:
                current = self.results[self._last_result_index]
                if not current.snippet:
                    self.results[self._last_result_index] = WebSearchResult(
                        title=current.title,
                        snippet=snippet,
                        url=current.url,
                    )
            self._capture_snippet = False
            self._current_snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_result_link:
            self._current_title_parts.append(data)
        elif self._capture_snippet:
            self._current_snippet_parts.append(data)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _ssl_context() -> ssl.SSLContext:
    """Use an explicit trusted bundle when the Python framework has no system roots."""
    configured_bundle = os.getenv("WEB_SEARCH_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    if configured_bundle:
        return ssl.create_default_context(cafile=configured_bundle)
    if _SYSTEM_CA_BUNDLE.is_file():
        return ssl.create_default_context(cafile=str(_SYSTEM_CA_BUNDLE))
    return ssl.create_default_context()


def _flatten_related_topics(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for item in items:
        if "Topics" in item:
            flat.extend(_flatten_related_topics(item["Topics"]))
        else:
            flat.append(item)
    return flat


def _extract_duckduckgo_target(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    parsed = urlparse(f"https:{href}" if href.startswith("//") else href)
    query_url = parse_qs(parsed.query).get("uddg")
    if query_url:
        return unquote(query_url[0])
    if href.startswith("//"):
        return f"https:{href}"
    return ""


def _build_search_queries(query: str) -> list[str]:
    cleaned = _clean_text(query)
    queries = [cleaned]

    terms = re.findall(r"[a-z0-9]+", cleaned.lower())
    reduced_terms = [term for term in terms if term not in _STOPWORDS]
    if reduced_terms:
        queries.append(" ".join(reduced_terms))

    if any(token in cleaned.lower() for token in {"stream", "watch", "available"}):
        title_guess = [term for term in reduced_terms if term not in {"streaming", "available"}]
        if title_guess:
            queries.append(f"{' '.join(title_guess)} where to watch streaming")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in queries:
        normalized = item.strip()
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped[:3]


def _fetch_json_search(query: str) -> list[WebSearchResult]:
    url = (
        "https://api.duckduckgo.com/?q="
        f"{quote_plus(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
    )
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(request, timeout=10, context=_ssl_context()) as response:  # noqa: S310 - controlled HTTPS URL
        payload = json.loads(response.read().decode("utf-8"))

    results: list[WebSearchResult] = []

    abstract_text = _clean_text(str(payload.get("AbstractText") or ""))
    abstract_url = str(payload.get("AbstractURL") or "").strip()
    heading = _clean_text(str(payload.get("Heading") or query))
    if abstract_text and abstract_url:
        results.append(WebSearchResult(title=heading or query, snippet=abstract_text, url=abstract_url))

    for item in _flatten_related_topics(payload.get("RelatedTopics") or []):
        text = _clean_text(str(item.get("Text") or ""))
        first_url = str(item.get("FirstURL") or "").strip()
        if text and first_url:
            title = text.split(" - ", 1)[0].strip()
            results.append(WebSearchResult(title=title or query, snippet=text, url=first_url))
        if len(results) >= 5:
            break

    return results


def _fetch_html_search(query: str) -> list[WebSearchResult]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(request, timeout=10, context=_ssl_context()) as response:  # noqa: S310 - controlled HTTPS URL
        page = response.read().decode("utf-8", errors="ignore")

    parser = _DuckDuckGoHtmlParser()
    parser.feed(page)
    results = [result for result in parser.results if result.title and result.url]
    return [
        WebSearchResult(
            title=result.title,
            snippet=result.snippet or result.title,
            url=result.url,
        )
        for result in results[:5]
    ]


def _dedupe_results(results: list[WebSearchResult]) -> list[WebSearchResult]:
    deduped: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for result in results:
        normalized_url = result.url.rstrip("/")
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        deduped.append(result)
    return deduped


def search_web(conversation_id: str, params: SearchWebInput) -> SearchWebOutput:
    with logged_tool_call("search_web", conversation_id):
        aggregated: list[WebSearchResult] = []

        for query in _build_search_queries(params.query):
            try:
                aggregated.extend(_fetch_json_search(query))
            except Exception as exc:  # Public providers can be unavailable or rate-limited.
                logger.warning("Web JSON search failed for %r: %s", query, exc)

            if len(aggregated) < 3:
                try:
                    aggregated.extend(_fetch_html_search(query))
                except Exception as exc:  # Keep the remaining provider/query attempts available.
                    logger.warning("Web HTML search failed for %r: %s", query, exc)

            deduped = _dedupe_results(aggregated)
            if len(deduped) >= 5:
                return SearchWebOutput(results=deduped[:5])
            aggregated = deduped

        return SearchWebOutput(results=aggregated[:5])
