"""019 — cortex episodic ticks and semantic stats.

Revision ID: 019
Revises: 018
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cortex_episodes",
        sa.Column("tick_id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("primed", JSONB, nullable=False, server_default="[]"),
        sa.Column("triggering", JSONB, nullable=False, server_default="[]"),
        sa.Column("phase", sa.String(length=32), nullable=False, server_default="cortex_v2"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cortex_episodes_as_of", "cortex_episodes", ["as_of"])

    op.create_table(
        "cortex_semantic_stats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("signal", sa.String(length=64), nullable=False),
        sa.Column("score_bucket", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("median_hours", sa.Float(), nullable=True),
        sa.Column("hit_rate", sa.Float(), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "metric",
            "signal",
            "score_bucket",
            name="uq_cortex_semantic_metric_signal_bucket",
        ),
    )


def downgrade() -> None:
    op.drop_table("cortex_semantic_stats")
    op.drop_index("ix_cortex_episodes_as_of", table_name="cortex_episodes")
    op.drop_table("cortex_episodes")
