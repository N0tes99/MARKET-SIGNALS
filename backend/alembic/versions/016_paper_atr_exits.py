"""016 — per-trade ATR paper exits.

Revision ID: 016
Revises: 015
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_trades",
        sa.Column("take_profit_pct", sa.Float(), nullable=False, server_default="6.0"),
    )
    op.add_column(
        "paper_trades",
        sa.Column("stop_loss_pct", sa.Float(), nullable=False, server_default="3.0"),
    )
    op.add_column(
        "paper_trades",
        sa.Column("stamp", sa.String(length=160), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("paper_trades", "stamp")
    op.drop_column("paper_trades", "stop_loss_pct")
    op.drop_column("paper_trades", "take_profit_pct")
