"""Add post moderation shred columns.

Revision ID: 007
Revises: 006
Create Date: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add shredded_at / shredded_by / body_sha256 for admin tombstones."""
    op.add_column(
        "posts",
        sa.Column("shredded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("shredded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("body_sha256", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_posts_shredded_by_user_id",
        "posts",
        "users",
        ["shredded_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_posts_shredded_at", "posts", ["shredded_at"])


def downgrade() -> None:
    """Drop shred columns."""
    op.drop_index("ix_posts_shredded_at", table_name="posts")
    op.drop_constraint("fk_posts_shredded_by_user_id", "posts", type_="foreignkey")
    op.drop_column("posts", "body_sha256")
    op.drop_column("posts", "shredded_by_user_id")
    op.drop_column("posts", "shredded_at")
