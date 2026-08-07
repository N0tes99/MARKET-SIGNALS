"""Asset discussion posts, social feed, likes, and follows."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_deps import get_optional_user, require_admin_user, require_verified_user
from app.core.dependencies import get_db
from app.market_data.symbols import is_tracked
from app.models.comment import Comment
from app.models.follow import Follow
from app.models.post import SHREDDED_POST_BODY, Post
from app.models.post_like import PostLike
from app.models.user import User
from app.schemas.social import (
    CommentSchema,
    CreateCommentRequest,
    CreateFeedPostRequest,
    CreatePostRequest,
    PostSchema,
    PublicProfileSchema,
    ShredPostRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

SHREDDED_COMMENT_BODY = "[removed]"


def _comment_schema(comment: Comment) -> CommentSchema:
    return CommentSchema(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        username=comment.author.username,
        body=comment.body,
        created_at=comment.created_at,
    )


def _post_schema(
    post: Post,
    *,
    liked_by_me: bool = False,
    like_count: int | None = None,
) -> PostSchema:
    comments = [] if post.is_shredded else [_comment_schema(c) for c in post.comments]
    likes = like_count if like_count is not None else len(post.likes)
    return PostSchema(
        id=post.id,
        user_id=post.user_id,
        username=post.author.username,
        symbol=post.symbol,
        body=post.body,
        created_at=post.created_at,
        comments=comments,
        comment_count=0 if post.is_shredded else len(post.comments),
        like_count=likes,
        liked_by_me=liked_by_me,
        is_shredded=post.is_shredded,
        shredded_at=post.shredded_at,
    )


async def _liked_post_ids(
    session: AsyncSession,
    user: User | None,
    post_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if user is None or not post_ids:
        return set()
    result = await session.execute(
        select(PostLike.post_id).where(
            PostLike.user_id == user.id,
            PostLike.post_id.in_(post_ids),
        )
    )
    return set(result.scalars().all())


def _reject_if_shredded(post: Post) -> None:
    if post.is_shredded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Post was removed by moderation",
        )


@router.get("/social/feed", response_model=list[PostSchema])
async def social_feed(
    session: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
    limit: int = 50,
) -> list[PostSchema]:
    """Recent posts across tracked symbols."""
    cap = max(1, min(limit, 100))
    result = await session.execute(
        select(Post)
        .options(
            selectinload(Post.author),
            selectinload(Post.comments).selectinload(Comment.author),
            selectinload(Post.likes),
        )
        .order_by(Post.created_at.desc())
        .limit(cap)
    )
    posts = list(result.scalars().unique().all())
    liked = await _liked_post_ids(session, viewer, [p.id for p in posts])
    return [_post_schema(p, liked_by_me=p.id in liked) for p in posts]


@router.post(
    "/social/posts",
    response_model=PostSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_feed_post(
    body: CreateFeedPostRequest,
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> PostSchema:
    """Create a post with a required tracked ticker."""
    normalized = body.symbol.upper().strip()
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
        like_count=0,
        liked_by_me=False,
        is_shredded=False,
        shredded_at=None,
    )


@router.get("/assets/{symbol}/posts", response_model=list[PostSchema])
async def list_posts(
    symbol: str,
    session: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> list[PostSchema]:
    """List discussion posts for a tracked symbol (newest first)."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Symbol '{normalized}' is not tracked")

    result = await session.execute(
        select(Post)
        .where(Post.symbol == normalized)
        .options(
            selectinload(Post.author),
            selectinload(Post.comments).selectinload(Comment.author),
            selectinload(Post.likes),
        )
        .order_by(Post.created_at.desc())
    )
    posts = list(result.scalars().unique().all())
    liked = await _liked_post_ids(session, viewer, [p.id for p in posts])
    return [_post_schema(p, liked_by_me=p.id in liked) for p in posts]


@router.post(
    "/assets/{symbol}/posts",
    response_model=PostSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_post(
    symbol: str,
    body: CreatePostRequest,
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> PostSchema:
    """Create a post on a tracked asset (verified login required)."""
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
        like_count=0,
        liked_by_me=False,
        is_shredded=False,
        shredded_at=None,
    )


@router.post("/posts/{post_id}/shred", response_model=PostSchema)
async def shred_post(
    post_id: uuid.UUID,
    body: ShredPostRequest | None = None,
    admin: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db),
) -> PostSchema:
    """Admin: wipe post text, leave a public tombstone (hash retained)."""
    result = await session.execute(
        select(Post)
        .where(Post.id == post_id)
        .options(
            selectinload(Post.author),
            selectinload(Post.comments).selectinload(Comment.author),
            selectinload(Post.likes),
        )
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.is_shredded:
        return _post_schema(post)

    reason = (body.reason if body else None) or ""
    digest = hashlib.sha256(post.body.encode("utf-8")).hexdigest()
    post.body_sha256 = digest
    post.body = SHREDDED_POST_BODY
    post.shredded_at = datetime.now(UTC)
    post.shredded_by_user_id = admin.id

    for comment in post.comments:
        comment.body = SHREDDED_COMMENT_BODY

    await session.flush()
    logger.info(
        "Post %s shredded by admin=%s reason=%r hash=%s",
        post.id,
        admin.username,
        reason[:200],
        digest[:12],
    )
    return _post_schema(post)


@router.get("/posts/{post_id}/comments", response_model=list[CommentSchema])
async def list_comments(
    post_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[CommentSchema]:
    """List comments for a post."""
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.is_shredded:
        return []

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
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> CommentSchema:
    """Add a comment to a post (verified login required)."""
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    _reject_if_shredded(post)

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


@router.post("/posts/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_post(
    post_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Like a post (idempotent)."""
    post = await session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    _reject_if_shredded(post)

    existing = await session.execute(
        select(PostLike).where(PostLike.user_id == user.id, PostLike.post_id == post_id)
    )
    if existing.scalar_one_or_none() is not None:
        return

    session.add(PostLike(user_id=user.id, post_id=post_id))
    await session.flush()


@router.delete("/posts/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_post(
    post_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Remove a like (idempotent)."""
    result = await session.execute(
        select(PostLike).where(PostLike.user_id == user.id, PostLike.post_id == post_id)
    )
    like = result.scalar_one_or_none()
    if like is not None:
        await session.delete(like)
        await session.flush()


@router.get("/users/{username}", response_model=PublicProfileSchema)
async def get_public_profile(
    username: str,
    session: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> PublicProfileSchema:
    """Light public profile by username."""
    result = await session.execute(
        select(User).where(func.lower(User.username) == username.lower().strip())
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    follower_count = await session.scalar(
        select(func.count()).select_from(Follow).where(Follow.following_id == user.id)
    )
    following_count = await session.scalar(
        select(func.count()).select_from(Follow).where(Follow.follower_id == user.id)
    )
    post_count = await session.scalar(
        select(func.count()).select_from(Post).where(Post.user_id == user.id)
    )

    followed_by_me = False
    if viewer is not None and viewer.id != user.id:
        follow = await session.execute(
            select(Follow).where(
                Follow.follower_id == viewer.id,
                Follow.following_id == user.id,
            )
        )
        followed_by_me = follow.scalar_one_or_none() is not None

    return PublicProfileSchema(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
        follower_count=int(follower_count or 0),
        following_count=int(following_count or 0),
        post_count=int(post_count or 0),
        followed_by_me=followed_by_me,
    )


@router.post("/users/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def follow_user(
    user_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Follow another user."""
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await session.execute(
        select(Follow).where(
            Follow.follower_id == user.id,
            Follow.following_id == user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return

    session.add(Follow(follower_id=user.id, following_id=user_id))
    await session.flush()


@router.delete("/users/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    user_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Unfollow a user."""
    result = await session.execute(
        select(Follow).where(
            Follow.follower_id == user.id,
            Follow.following_id == user_id,
        )
    )
    follow = result.scalar_one_or_none()
    if follow is not None:
        await session.delete(follow)
        await session.flush()
