"""Initial evidence_snapshots table.

Revision ID: 001
Revises:
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create evidence_snapshots table."""
    op.create_table(
        "evidence_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False, server_default="1h"),
        sa.Column("total_confidence", sa.Float(), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_evidence_snapshots_symbol", "evidence_snapshots", ["symbol"])


def downgrade() -> None:
    """Drop evidence_snapshots table."""
    op.drop_index("ix_evidence_snapshots_symbol", table_name="evidence_snapshots")
    op.drop_table("evidence_snapshots")
