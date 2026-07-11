"""add film.streaming_available

Revision ID: 0001
Revises:
Create Date: 2026-07-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ## here we assume that film table already exists, and we are just adding a new column (streaming_available) to it.
    ## server_default=sa.false() lets Postgres fill existing rows with FALSE for the new column, so that the migration doesn't fail due to NULL values in a non-nullable column.
    ## nullable=False makes the column required
    
    op.add_column(
        "film",
        sa.Column("streaming_available", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    # Seed a plausible mix of streaming availability for local testing/demo purposes.
    op.execute("UPDATE film SET streaming_available = TRUE WHERE film_id % 3 = 0")
    op.execute("UPDATE film SET streaming_available = TRUE WHERE title ILIKE 'ALIEN%'")


def downgrade() -> None:
    op.drop_column("film", "streaming_available")
