"""create streaming_subscription

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "streaming_subscription",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id",
            sa.SmallInteger(),
            sa.ForeignKey("customer.customer_id"),
            nullable=False,
        ),
        sa.Column("plan_name", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    
    ## create index for faster lookups on customer_id, since we will often query subscriptions by customer_id.
    op.create_index(
        "ix_streaming_subscription_customer_id", "streaming_subscription", ["customer_id"]
    )

    # Seed at least one subscription for local testing.
    op.execute(
        """
        INSERT INTO streaming_subscription
            (customer_id, plan_name, status, start_date, end_date, auto_renew)
        VALUES
            (1, 'Premium', 'active', '2026-01-01', NULL, TRUE),
            (2, 'Basic', 'cancelled', '2025-06-01', '2026-06-01', FALSE),
            (3, 'Standard', 'trial', '2026-03-15', '2026-04-15', FALSE)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_streaming_subscription_customer_id", table_name="streaming_subscription")
    op.drop_table("streaming_subscription")
