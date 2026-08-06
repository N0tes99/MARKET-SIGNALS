"""Discussion post/comment schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreatePostRequest(BaseModel):
    """Create a post (body only; symbol comes from path or feed compose)."""

    body: str = Field(min_length=1, max_length=2000)


class CreateFeedPostRequest(BaseModel):
    """Create a social-feed post with required ticker."""

    symbol: str = Field(min_length=1, max_length=20)
    body: str = Field(min_length=1, max_length=2000)


class CreateCommentRequest(BaseModel):
    """Create a comment on a post."""

    body: str = Field(min_length=1, max_length=1000)


class CommentSchema(BaseModel):
    """Comment with author username."""

    id: uuid.UUID
    post_id: uuid.UUID
    user_id: uuid.UUID
    username: str
    body: str
    created_at: datetime


class PostSchema(BaseModel):
    """Post with author username, engagement, and nested comments."""

    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    symbol: str
    body: str
    created_at: datetime
    comments: list[CommentSchema] = Field(default_factory=list)
    comment_count: int = 0
    like_count: int = 0
    liked_by_me: bool = False


class PublicProfileSchema(BaseModel):
    """Light public profile for follow UI."""

    id: uuid.UUID
    username: str
    created_at: datetime
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    followed_by_me: bool = False


class FavoriteSchema(BaseModel):
    """A favorited tracked symbol."""

    symbol: str
    created_at: datetime


class AddFavoriteRequest(BaseModel):
    """Add a favorite symbol."""

    symbol: str = Field(min_length=1, max_length=20)
