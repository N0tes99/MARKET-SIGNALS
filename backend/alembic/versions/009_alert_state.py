"""009 — durable Discord alert cooldown + snapshots.

Revision ID: 009
Revises: 008
Create Date: 2026-08-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_state",
        sa.Column("symbol", sa.String(length=20), primary_key=True, nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("trade_grade", sa.String(length=10), nullable=False),
        sa.Column("trend", sa.String(length=32), nullable=False),
        sa.Column("trade_state", sa.String(length=20), nullable=False),
        sa.Column("execution_signal", sa.String(length=20), nullable=False),
        sa.Column("expected_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alert_state_last_sent_at", "alert_state", ["last_sent_at"])


def downgrade() -> None:
    op.drop_index("ix_alert_state_last_sent_at", table_name="alert_state")
    op.drop_table("alert_state")
