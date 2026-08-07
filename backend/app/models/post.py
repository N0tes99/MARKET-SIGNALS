"""Discussion post ORM model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

# Public placeholder after admin shred — original text is wiped.
SHREDDED_POST_BODY = "[removed by moderation]"


class Post(Base):
    """Asset discussion post."""

    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    shredded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    shredded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # SHA-256 of original body (hex) — no plaintext retained after shred
    body_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    author: Mapped["User"] = relationship(  # noqa: F821
        back_populates="posts",
        foreign_keys=[user_id],
    )
    comments: Mapped[list["Comment"]] = relationship(  # noqa: F821
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )
    likes: Mapped[list["PostLike"]] = relationship(  # noqa: F821
        back_populates="post",
        cascade="all, delete-orphan",
    )

    @property
    def is_shredded(self) -> bool:
        return self.shredded_at is not None
