"""017 — persist scoring weight overrides.

Revision ID: 017
Revises: 016
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "weight_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("preset", sa.String(length=64), nullable=False),
        sa.Column("weights", JSONB(), nullable=False),
        sa.Column("regime_auto", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("weight_overrides")
