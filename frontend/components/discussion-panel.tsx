"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import {
  createAssetPost,
  createPostComment,
  fetchAssetPosts,
  type DiscussionPost,
} from "@/services/api";

interface DiscussionPanelProps {
  symbol: string;
}

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

function PostCard({
  post,
  canComment,
  onComment,
  pending,
}: {
  post: DiscussionPost;
  canComment: boolean;
  onComment: (postId: string, body: string) => Promise<void>;
  pending: boolean;
}) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submitComment(event: FormEvent) {
    event.preventDefault();
    const body = draft.trim();
    if (!body) return;
    setError(null);
    try {
      await onComment(post.id, body);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to comment");
    }
  }

  return (
    <article className="border-t border-white/[0.06] pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-mono text-xs text-foreground">{post.username}</span>
        <time className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {formatWhen(post.created_at)}
        </time>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
        {post.body}
      </p>

      {post.comments.length > 0 ? (
        <ul className="mt-3 space-y-2 border-l border-white/[0.08] pl-3">
          {post.comments.map((comment) => (
            <li key={comment.id}>
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-mono text-[11px] text-foreground/80">
                  {comment.username}
                </span>
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

      {canComment ? (
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
          {error ? <p className="text-sm text-bearish sm:basis-full">{error}</p> : null}
        </form>
      ) : null}
    </article>
  );
}

export function DiscussionPanel({ symbol }: DiscussionPanelProps) {
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);

  const postsQuery = useQuery({
    queryKey: ["posts", symbol],
    queryFn: () => fetchAssetPosts(symbol),
  });

  const postMutation = useMutation({
    mutationFn: (text: string) => createAssetPost(symbol, text),
    onSuccess: () => {
      setBody("");
      void queryClient.invalidateQueries({ queryKey: ["posts", symbol] });
    },
  });

  const commentMutation = useMutation({
    mutationFn: ({ postId, text }: { postId: string; text: string }) =>
      createPostComment(postId, text),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["posts", symbol] });
    },
  });

  async function onCreatePost(event: FormEvent) {
    event.preventDefault();
    const text = body.trim();
    if (!text) return;
    setError(null);
    try {
      await postMutation.mutateAsync(text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to post");
    }
  }

  const posts = postsQuery.data ?? [];

  return (
    <section className="surface mt-3 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="label-caps">Discussion</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Share thesis notes on {symbol}. Public to read; sign in to post.
          </p>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {posts.length} post{posts.length === 1 ? "" : "s"}
        </span>
      </div>

      {!authLoading && !user ? (
        <p className="mt-4 border-t border-white/[0.06] pt-4 text-sm text-muted-foreground">
          <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
            Sign in
          </Link>{" "}
          or{" "}
          <Link href="/register" className="text-foreground underline-offset-4 hover:underline">
            create an account
          </Link>{" "}
          to join the discussion.
        </p>
      ) : null}

      {user ? (
        <form onSubmit={onCreatePost} className="mt-4 border-t border-white/[0.06] pt-4">
          <label className="block">
            <span className="label-caps">New post</span>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              maxLength={2000}
              rows={3}
              placeholder="What's your read on this asset?"
              className="mt-2 w-full resize-y border border-white/[0.1] bg-transparent px-3 py-2 text-sm outline-none focus:border-white/[0.22]"
            />
          </label>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <span className="font-mono text-[10px] text-muted-foreground">
              {body.length}/2000
            </span>
            <button
              type="submit"
              disabled={postMutation.isPending || !body.trim()}
              className="border border-white/[0.1] px-3 py-2 font-mono text-xs uppercase tracking-wide transition-colors hover:bg-white/[0.06] disabled:opacity-50"
            >
              {postMutation.isPending ? "Posting…" : "Post"}
            </button>
          </div>
          {error ? <p className="mt-2 text-sm text-bearish">{error}</p> : null}
        </form>
      ) : null}

      <div className="mt-5 space-y-4">
        {postsQuery.isLoading ? (
          <p className="font-mono text-xs text-muted-foreground">Loading discussion…</p>
        ) : null}
        {postsQuery.isError ? (
          <p className="text-sm text-bearish">Could not load discussion.</p>
        ) : null}
        {!postsQuery.isLoading && posts.length === 0 ? (
          <p className="text-sm text-muted-foreground">No posts yet — start the thread.</p>
        ) : null}
        {posts.map((post) => (
          <PostCard
            key={post.id}
            post={post}
            canComment={Boolean(user)}
            pending={commentMutation.isPending}
            onComment={async (postId, text) => {
              await commentMutation.mutateAsync({ postId, text });
            }}
          />
        ))}
      </div>
    </section>
  );
}
