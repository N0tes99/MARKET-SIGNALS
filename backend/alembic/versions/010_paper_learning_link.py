"""010 — link paper trades into learning memory.

Revision ID: 010
Revises: 009
Create Date: 2026-08-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "signal_records",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="dashboard"),
    )
    op.add_column(
        "signal_records",
        sa.Column("paper_trade_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "signal_records",
        sa.Column("ledger", sa.String(length=16), nullable=True),
    )
    op.create_index("ix_signal_records_source", "signal_records", ["source"])
    op.create_index("ix_signal_records_paper_trade_id", "signal_records", ["paper_trade_id"])

    op.add_column(
        "paper_trades",
        sa.Column("signal_record_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_paper_trades_signal_record_id", "paper_trades", ["signal_record_id"])


def downgrade() -> None:
    op.drop_index("ix_paper_trades_signal_record_id", table_name="paper_trades")
    op.drop_column("paper_trades", "signal_record_id")
    op.drop_index("ix_signal_records_paper_trade_id", table_name="signal_records")
    op.drop_index("ix_signal_records_source", table_name="signal_records")
    op.drop_column("signal_records", "ledger")
    op.drop_column("signal_records", "paper_trade_id")
    op.drop_column("signal_records", "source")
