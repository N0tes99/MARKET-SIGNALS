"""020 — procedural expansion knobs and OHLCV warehouse bars.

Revision ID: 020
Revises: 019
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "procedural_policies",
        sa.Column("name", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("knobs", JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ohlcv_bars",
        sa.Column("symbol", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("timeframe", sa.String(length=8), primary_key=True, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="live"),
    )


def downgrade() -> None:
    op.drop_table("ohlcv_bars")
    op.drop_table("procedural_policies")
