"""Asset discussion posts and comments."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_deps import get_current_user
from app.core.dependencies import get_db
from app.market_data.symbols import is_tracked
from app.models.comment import Comment
from app.models.post import Post
from app.models.user import User
from app.schemas.social import (
    CommentSchema,
    CreateCommentRequest,
    CreatePostRequest,
    PostSchema,
)

router = APIRouter()


def _comment_schema(comment: Comment) -> CommentSchema:
    return CommentSchema(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        username=comment.author.username,
        body=comment.body,
        created_at=comment.created_at,
    )


def _post_schema(post: Post) -> PostSchema:
    comments = [_comment_schema(c) for c in post.comments]
    return PostSchema(
        id=post.id,
        user_id=post.user_id,
        username=post.author.username,
        symbol=post.symbol,
        body=post.body,
        created_at=post.created_at,
        comments=comments,
        comment_count=len(comments),
    )


@router.get("/assets/{symbol}/posts", response_model=list[PostSchema])
async def list_posts(
    symbol: str,
    session: AsyncSession = Depends(get_db),
) -> list[PostSchema]:
    """List discussion posts for a tracked symbol (newest first)."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Symbol '{normalized}' is not tracked")

    result = await session.execute(
        select(Post)
        .where(Post.symbol == normalized)
        .options(selectinload(Post.author), selectinload(Post.comments).selectinload(Comment.author))
        .order_by(Post.created_at.desc())
    )
    posts = result.scalars().unique().all()
    return [_post_schema(p) for p in posts]


@router.post(
    "/assets/{symbol}/posts",
    response_model=PostSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_post(
    symbol: str,
    body: CreatePostRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PostSchema:
    """Create a post on a tracked asset (login required)."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{normalized}' is not tracked",
        )

    post = Post(
        user_id=user.id,
        symbol=normalized,
        body=body.body.strip(),
    )
    session.add(post)
    await session.flush()
    return PostSchema(
        id=post.id,
        user_id=user.id,
        username=user.username,
        symbol=post.symbol,
        body=post.body,
        created_at=post.created_at,
        comments=[],
        comment_count=0,
    )


@router.get("/posts/{post_id}/comments", response_model=list[CommentSchema])
async def list_comments(
    post_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[CommentSchema]:
    """List comments for a post."""
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    result = await session.execute(
        select(Comment)
        .where(Comment.post_id == post_id)
        .options(selectinload(Comment.author))
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    return [_comment_schema(c) for c in comments]


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    post_id: uuid.UUID,
    body: CreateCommentRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CommentSchema:
    """Add a comment to a post (login required)."""
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    comment = Comment(
        post_id=post_id,
        user_id=user.id,
        body=body.body.strip(),
    )
    session.add(comment)
    await session.flush()
    return CommentSchema(
        id=comment.id,
        post_id=comment.post_id,
        user_id=user.id,
        username=user.username,
        body=comment.body,
        created_at=comment.created_at,
    )
