from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import (
    GetCustomerRentalHistoryInput,
    GetCustomerRentalHistoryOutput,
    RentalRecord,
)
from app.tools.base import ToolMetadata, logged_tool_call


METADATA = ToolMetadata(
    name="get_customer_rental_history",
    description="Return a customer's most recent rentals (film title, rental date, return date).",
    input_schema=GetCustomerRentalHistoryInput.model_json_schema(),
    output_schema=GetCustomerRentalHistoryOutput.model_json_schema(),
    error_behavior="Returns an empty rentals list when the customer has no rental history; "
    "never raises for a customer with zero rentals.",
    auth_requirement="caller must supply the requesting customer's own customer_id",
    ownership_boundary="Reads only from rental/inventory/film joined by customer_id; no writes.",
    backed_by="postgres:pagila",
)

_QUERY = text(
    """
    SELECT f.title, r.rental_date, r.return_date
    FROM rental r
    JOIN inventory i ON i.inventory_id = r.inventory_id
    JOIN film f ON f.film_id = i.film_id
    WHERE r.customer_id = :customer_id
    ORDER BY r.rental_date DESC
    LIMIT :limit
    """
)


def get_customer_rental_history(
    session: Session, conversation_id: str, params: GetCustomerRentalHistoryInput
) -> GetCustomerRentalHistoryOutput:
    with logged_tool_call("get_customer_rental_history", conversation_id):
        rows = (
            session.execute(_QUERY, {"customer_id": params.customer_id, "limit": params.limit})
            .mappings()
            .all()
        )
        rentals = [RentalRecord(**row) for row in rows]
        return GetCustomerRentalHistoryOutput(rentals=rentals)
