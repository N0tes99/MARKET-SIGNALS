"""015 — ticker requests from users to admin.

Revision ID: 015
Revises: 014
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticker_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticker_requests_user_id", "ticker_requests", ["user_id"])
    op.create_index("ix_ticker_requests_symbol", "ticker_requests", ["symbol"])
    op.create_index("ix_ticker_requests_created_at", "ticker_requests", ["created_at"])
    op.create_index("ix_ticker_requests_status", "ticker_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ticker_requests_status", table_name="ticker_requests")
    op.drop_index("ix_ticker_requests_created_at", table_name="ticker_requests")
    op.drop_index("ix_ticker_requests_symbol", table_name="ticker_requests")
    op.drop_index("ix_ticker_requests_user_id", table_name="ticker_requests")
    op.drop_table("ticker_requests")
