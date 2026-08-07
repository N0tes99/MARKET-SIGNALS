"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import { SocialPostCard } from "@/components/social-post-card";
import { createAssetPost, fetchAssetPosts } from "@/services/api";

interface DiscussionPanelProps {
  symbol: string;
}

export function DiscussionPanel({ symbol }: DiscussionPanelProps) {
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const canWrite = Boolean(user?.email_verified);

  const postsQuery = useQuery({
    queryKey: ["posts", symbol],
    queryFn: () => fetchAssetPosts(symbol),
  });

  const postMutation = useMutation({
    mutationFn: (text: string) => createAssetPost(symbol, text),
    onSuccess: () => {
      setBody("");
      void queryClient.invalidateQueries({ queryKey: ["posts", symbol] });
      void queryClient.invalidateQueries({ queryKey: ["social-feed"] });
    },
  });

  async function onCreatePost(event: FormEvent) {
    event.preventDefault();
    const text = body.trim();
    if (!text || !canWrite) return;
    setError(null);
    try {
      await postMutation.mutateAsync(text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to post");
    }
  }

  const posts = postsQuery.data ?? [];

  return (
    <section className="surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="label-caps">Discussion</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Share thesis notes on {symbol}. Public to read; verified account to post.
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

      {user && !user.email_verified ? (
        <p className="mt-4 border-t border-white/[0.06] pt-4 text-sm text-muted-foreground">
          Confirm your email before posting.{" "}
          <Link href="/verify-email" className="text-foreground underline-offset-4 hover:underline">
            Verify email
          </Link>
        </p>
      ) : null}

      {canWrite ? (
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
          <SocialPostCard
            key={post.id}
            post={post}
            showTickerLink={false}
            onChanged={() => {
              void queryClient.invalidateQueries({ queryKey: ["posts", symbol] });
            }}
          />
        ))}
      </div>
    </section>
  );
}
