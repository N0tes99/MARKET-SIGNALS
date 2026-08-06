"""Add email verification columns to users.

Revision ID: 004
Revises: 003
Create Date: 2026-08-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add verification fields; mark existing users verified."""
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verify_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verify_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Existing accounts stay usable
    op.execute("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")


def downgrade() -> None:
    """Drop verification columns."""
    op.drop_column("users", "email_verify_sent_at")
    op.drop_column("users", "email_verify_token_hash")
    op.drop_column("users", "email_verified_at")
