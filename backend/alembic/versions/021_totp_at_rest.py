"""021 — encrypt TOTP secrets at rest; replay counter; session version.

Widens users.totp_secret for sealed blobs, records the last accepted
timestep so a captured 6-digit code cannot be replayed, and adds
session_version so logout / password reset invalidate stolen JWTs.

Revision ID: 021
Revises: 020
Create Date: 2026-09-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "totp_secret",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.add_column("users", sa.Column("totp_last_step", sa.BigInteger(), nullable=True))
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
    op.drop_column("users", "totp_last_step")
    op.alter_column(
        "users",
        "totp_secret",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
