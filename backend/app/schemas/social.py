"""Discussion post/comment schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreatePostRequest(BaseModel):
    """Create a post on an asset page."""

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
    """Post with author username and nested comments."""

    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    symbol: str
    body: str
    created_at: datetime
    comments: list[CommentSchema] = Field(default_factory=list)
    comment_count: int = 0
