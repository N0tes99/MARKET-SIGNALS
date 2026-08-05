"""Create signal_records table.

Revision ID: 002
Revises: 001
Create Date: 2026-08-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create signal_records table."""
    op.create_table(
        "signal_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("trade_grade", sa.String(length=10), nullable=False),
        sa.Column("trade_state", sa.String(length=20), nullable=False),
        sa.Column("execution_signal", sa.String(length=20), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("category_scores", postgresql.JSONB(), nullable=False),
        sa.Column("expected_value", sa.Float(), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=True),
        sa.Column("realized_return_pct", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_signal_records_symbol", "signal_records", ["symbol"])
    op.create_index("ix_signal_records_timestamp", "signal_records", ["timestamp"])
    op.create_index("ix_signal_records_outcome", "signal_records", ["outcome"])


def downgrade() -> None:
    """Drop signal_records table."""
    op.drop_index("ix_signal_records_outcome", table_name="signal_records")
    op.drop_index("ix_signal_records_timestamp", table_name="signal_records")
    op.drop_index("ix_signal_records_symbol", table_name="signal_records")
    op.drop_table("signal_records")
