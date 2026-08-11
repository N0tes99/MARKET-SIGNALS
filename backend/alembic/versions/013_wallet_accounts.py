"""013 — wallet accounts + auth challenges (Ethereum W1).

Revision ID: 013
Revises: 012
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallet_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chain", "address", name="uq_wallet_accounts_chain_address"),
    )
    op.create_index("ix_wallet_accounts_user_id", "wallet_accounts", ["user_id"])
    op.create_index("ix_wallet_accounts_chain", "wallet_accounts", ["chain"])
    op.create_index("ix_wallet_accounts_address", "wallet_accounts", ["address"])

    op.create_table(
        "wallet_auth_challenges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("chain", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=128), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("message", sa.String(length=2048), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nonce"),
    )
    op.create_index("ix_wallet_auth_challenges_chain", "wallet_auth_challenges", ["chain"])
    op.create_index(
        "ix_wallet_auth_challenges_address", "wallet_auth_challenges", ["address"]
    )
    op.create_index(
        "ix_wallet_auth_challenges_expires_at",
        "wallet_auth_challenges",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_auth_challenges_expires_at", table_name="wallet_auth_challenges")
    op.drop_index("ix_wallet_auth_challenges_address", table_name="wallet_auth_challenges")
    op.drop_index("ix_wallet_auth_challenges_chain", table_name="wallet_auth_challenges")
    op.drop_table("wallet_auth_challenges")
    op.drop_index("ix_wallet_accounts_address", table_name="wallet_accounts")
    op.drop_index("ix_wallet_accounts_chain", table_name="wallet_accounts")
    op.drop_index("ix_wallet_accounts_user_id", table_name="wallet_accounts")
    op.drop_table("wallet_accounts")
