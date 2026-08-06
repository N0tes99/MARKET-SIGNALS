"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  createPostComment,
  followUser,
  likePost,
  unfollowUser,
  unlikePost,
  type DiscussionPost,
} from "@/services/api";

function formatWhen(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

interface SocialPostCardProps {
  post: DiscussionPost;
  onChanged?: () => void;
  showTickerLink?: boolean;
}

export function SocialPostCard({
  post,
  onChanged,
  showTickerLink = true,
}: SocialPostCardProps) {
  const { user } = useAuth();
  const canWrite = Boolean(user?.email_verified);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [liked, setLiked] = useState(post.liked_by_me);
  const [likeCount, setLikeCount] = useState(post.like_count);
  const [following, setFollowing] = useState(false);

  async function toggleLike() {
    if (!canWrite) return;
    setPending(true);
    setError(null);
    try {
      if (liked) {
        await unlikePost(post.id);
        setLiked(false);
        setLikeCount((n) => Math.max(0, n - 1));
      } else {
        await likePost(post.id);
        setLiked(true);
        setLikeCount((n) => n + 1);
      }
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Like failed");
    } finally {
      setPending(false);
    }
  }

  async function toggleFollow() {
    if (!canWrite || !user || user.id === post.user_id) return;
    setPending(true);
    setError(null);
    try {
      if (following) {
        await unfollowUser(post.user_id);
        setFollowing(false);
      } else {
        await followUser(post.user_id);
        setFollowing(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Follow failed");
    } finally {
      setPending(false);
    }
  }

  async function submitComment(event: FormEvent) {
    event.preventDefault();
    if (!canWrite) return;
    const body = draft.trim();
    if (!body) return;
    setPending(true);
    setError(null);
    try {
      await createPostComment(post.id, body);
      setDraft("");
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to comment");
    } finally {
      setPending(false);
    }
  }

  return (
    <article className="border-t border-white/[0.06] pt-4 first:border-t-0 first:pt-0">
      <div className="flex gap-3">
        {showTickerLink ? (
          <Link
            href={`/assets/${post.symbol}`}
            className="flex h-14 w-14 shrink-0 flex-col items-center justify-center border border-white/[0.1] bg-white/[0.03] transition-colors hover:bg-white/[0.06]"
          >
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              ticker
            </span>
            <span className="font-mono text-sm text-foreground">{post.symbol}</span>
          </Link>
        ) : null}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={`/u/${encodeURIComponent(post.username)}`}
                className="font-mono text-xs text-foreground underline-offset-4 hover:underline"
              >
                {post.username}
              </Link>
              {user && user.id !== post.user_id && canWrite ? (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => void toggleFollow()}
                  className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground disabled:opacity-50"
                >
                  {following ? "Following" : "Follow"}
                </button>
              ) : null}
            </div>
            <time className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              {formatWhen(post.created_at)}
            </time>
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
            {post.body}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={!canWrite || pending}
              onClick={() => void toggleLike()}
              className={`font-mono text-[11px] uppercase tracking-wide transition-colors disabled:opacity-40 ${
                liked ? "text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {liked ? "Liked" : "Like"} · {likeCount}
            </button>
            <span className="font-mono text-[11px] text-muted-foreground">
              {post.comment_count} comment{post.comment_count === 1 ? "" : "s"}
            </span>
          </div>

          {post.comments.length > 0 ? (
            <ul className="mt-3 space-y-2 border-l border-white/[0.08] pl-3">
              {post.comments.map((comment) => (
                <li key={comment.id}>
                  <div className="flex flex-wrap items-baseline gap-2">
                    <Link
                      href={`/u/${encodeURIComponent(comment.username)}`}
                      className="font-mono text-[11px] text-foreground/80 underline-offset-4 hover:underline"
                    >
                      {comment.username}
                    </Link>
                    <time className="font-mono text-[10px] text-muted-foreground">
                      {formatWhen(comment.created_at)}
                    </time>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
                    {comment.body}
                  </p>
                </li>
              ))}
            </ul>
          ) : null}

          {canWrite ? (
            <form onSubmit={submitComment} className="mt-3 flex flex-col gap-2 sm:flex-row">
              <input
                type="text"
                maxLength={1000}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Add a comment"
                className="min-w-0 flex-1 border border-white/[0.1] bg-transparent px-3 py-2 text-sm outline-none focus:border-white/[0.22]"
              />
              <button
                type="submit"
                disabled={pending || !draft.trim()}
                className="border border-white/[0.1] px-3 py-2 font-mono text-[11px] uppercase tracking-wide transition-colors hover:bg-white/[0.06] disabled:opacity-50"
              >
                Reply
              </button>
            </form>
          ) : user && !user.email_verified ? (
            <p className="mt-3 text-xs text-muted-foreground">
              <Link href="/verify-email" className="underline-offset-4 hover:underline">
                Verify your email
              </Link>{" "}
              to like or comment.
            </p>
          ) : null}

          {error ? <p className="mt-2 text-sm text-bearish">{error}</p> : null}
        </div>
      </div>
    </article>
  );
}
