from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import (
    GetCustomerStreamingSubscriptionInput,
    GetCustomerStreamingSubscriptionOutput,
)
from app.tools.base import ToolError, ToolMetadata, logged_tool_call


METADATA = ToolMetadata(
    name="get_customer_streaming_subscription",
    description="Look up a customer's streaming subscription status, plan, renewal date, "
    "and auto-renew flag.",
    input_schema=GetCustomerStreamingSubscriptionInput.model_json_schema(),
    output_schema=GetCustomerStreamingSubscriptionOutput.model_json_schema(),
    error_behavior="Raises ToolError(code='not_found') when the customer has no subscription "
    "row; callers must handle this without exposing other customers' data.",
    auth_requirement="caller must supply the requesting customer's own customer_id",
    ownership_boundary="Reads only from streaming_subscription, scoped to a single customer_id.",
    backed_by="postgres:pagila (streaming_subscription, added by migration)",
)

_QUERY = text(
    """
    SELECT plan_name, status, start_date, end_date, auto_renew
    FROM streaming_subscription
    WHERE customer_id = :customer_id
    ORDER BY start_date DESC
    LIMIT 1
    """
)


def get_customer_streaming_subscription(
    session: Session, conversation_id: str, params: GetCustomerStreamingSubscriptionInput
) -> GetCustomerStreamingSubscriptionOutput:
    with logged_tool_call("get_customer_streaming_subscription", conversation_id):
        row = session.execute(_QUERY, {"customer_id": params.customer_id}).mappings().first()
        if row is None:
            raise ToolError("not_found", f"No subscription found for customer_id={params.customer_id}")
        return GetCustomerStreamingSubscriptionOutput(**row)
