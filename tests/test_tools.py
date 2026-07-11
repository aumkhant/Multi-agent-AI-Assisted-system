from datetime import date
from unittest.mock import MagicMock

import pytest

from app.schemas import (
    CreateHandoffTicketInput,
    GetCustomerStreamingSubscriptionInput,
    SearchFilmCatalogInput,
    SearchKbInput,
)
from app.tools.base import ToolError
from app.tools.catalog import search_film_catalog
from app.tools.handoff import create_handoff_ticket, list_tickets
from app.tools.knowledge_base import search_kb
from app.tools.subscription import get_customer_streaming_subscription


def _mock_session(rows):
    session = MagicMock()
    session.execute.return_value.mappings.return_value.all.return_value = rows
    session.execute.return_value.mappings.return_value.first.return_value = (
        rows[0] if rows else None
    )
    return session


def test_search_film_catalog_maps_rows_to_typed_results():
    session = _mock_session(
        [
            {
                "title": "ALIEN CENTER",
                "category": "Documentary",
                "rating": "PG",
                "rental_rate": 2.99,
                "streaming_available": True,
            }
        ]
    )
    result = search_film_catalog(session, "conv-1", SearchFilmCatalogInput(query="alien"))
    assert len(result.results) == 1
    assert result.results[0].title == "ALIEN CENTER"
    assert result.results[0].streaming_available is True


def test_search_film_catalog_empty_results_does_not_raise():
    session = _mock_session([])
    result = search_film_catalog(session, "conv-1", SearchFilmCatalogInput(query="zzz-no-match"))
    assert result.results == []


def test_get_customer_streaming_subscription_not_found_raises_tool_error():
    session = _mock_session([])
    with pytest.raises(ToolError) as exc_info:
        get_customer_streaming_subscription(
            session, "conv-1", GetCustomerStreamingSubscriptionInput(customer_id=99999)
        )
    assert exc_info.value.code == "not_found"


def test_get_customer_streaming_subscription_found():
    session = _mock_session(
        [
            {
                "plan_name": "Premium",
                "status": "active",
                "start_date": date(2026, 1, 1),
                "end_date": None,
                "auto_renew": True,
            }
        ]
    )
    result = get_customer_streaming_subscription(
        session, "conv-1", GetCustomerStreamingSubscriptionInput(customer_id=1)
    )
    assert result.status == "active"
    assert result.auto_renew is True


def test_search_kb_returns_relevant_article_with_source():
    result = search_kb("conv-1", SearchKbInput(query="how do I update my payment method"))
    assert result.articles
    assert result.articles[0].source == "updating-payment-method.md"


def test_search_kb_no_match_returns_empty():
    result = search_kb("conv-1", SearchKbInput(query="xyzzy quux unmatched gibberish term"))
    assert result.articles == []


def test_create_handoff_ticket_creates_a_ticket():
    before = len(list_tickets())
    result = create_handoff_ticket(
        "conv-1", CreateHandoffTicketInput(summary="wants to cancel", reason="sensitive_mutation")
    )
    assert result.status == "open"
    assert result.ticket_id.startswith("HAND-")
    assert len(list_tickets()) == before + 1
