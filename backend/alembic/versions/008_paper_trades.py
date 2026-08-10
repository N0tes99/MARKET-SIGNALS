"""008 — durable paper_trades + paper_agent_state for public PnL.

Revision ID: 008
Revises: 007
Create Date: 2026-08-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("setup_type", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("signal_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("size_usd", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("optimistic_entry", sa.Float(), nullable=False),
        sa.Column("optimistic_entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("optimistic_exit", sa.Float(), nullable=True),
        sa.Column("optimistic_pnl_usd", sa.Float(), nullable=True),
        sa.Column("optimistic_return_pct", sa.Float(), nullable=True),
        sa.Column("honest_entry", sa.Float(), nullable=True),
        sa.Column("honest_entry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("honest_bar_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("honest_exit", sa.Float(), nullable=True),
        sa.Column("honest_pnl_usd", sa.Float(), nullable=True),
        sa.Column("honest_return_pct", sa.Float(), nullable=True),
        sa.Column("mark_price", sa.Float(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(length=128), nullable=True),
        sa.Column("factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_paper_trades_symbol", "paper_trades", ["symbol"])
    op.create_index("ix_paper_trades_fingerprint", "paper_trades", ["fingerprint"])
    op.create_index("ix_paper_trades_signal_at", "paper_trades", ["signal_at"])
    op.create_index("ix_paper_trades_status", "paper_trades", ["status"])

    op.create_table(
        "paper_agent_state",
        sa.Column("key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("paper_agent_state")
    op.drop_index("ix_paper_trades_status", table_name="paper_trades")
    op.drop_index("ix_paper_trades_signal_at", table_name="paper_trades")
    op.drop_index("ix_paper_trades_fingerprint", table_name="paper_trades")
    op.drop_index("ix_paper_trades_symbol", table_name="paper_trades")
    op.drop_table("paper_trades")
