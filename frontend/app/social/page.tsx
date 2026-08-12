"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import { SocialPostCard } from "@/components/social-post-card";
import { TRACKED_SYMBOLS } from "@/config/assets";
import { createFeedPost, fetchSocialFeed } from "@/services/api";

export default function SocialPage() {
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = useState<string>(TRACKED_SYMBOLS[0] ?? "BTC");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const canWrite = Boolean(user?.email_verified);

  const feedQuery = useQuery({
    queryKey: ["social-feed"],
    queryFn: fetchSocialFeed,
  });

  const postMutation = useMutation({
    mutationFn: ({ sym, text }: { sym: string; text: string }) => createFeedPost(sym, text),
    onSuccess: () => {
      setBody("");
      void queryClient.invalidateQueries({ queryKey: ["social-feed"] });
    },
  });

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canWrite || !body.trim()) return;
    setError(null);
    try {
      await postMutation.mutateAsync({ sym: symbol, text: body.trim() });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to post");
    }
  }

  const posts = feedQuery.data ?? [];

  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto max-w-2xl px-4 py-10">
        <p className="label-caps">Community</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Social</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Posts require a tracked ticker as the visual. Like, comment, or follow others.
        </p>

        {!authLoading && !user ? (
          <p className="surface mt-6 p-4 text-sm text-muted-foreground">
            <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
              Sign in
            </Link>{" "}
            to read and post. Social is invite-only with the rest of the product.
          </p>
        ) : null}

        {user && !user.email_verified ? (
          <p className="surface mt-6 p-4 text-sm text-muted-foreground">
            Verify your email before posting.{" "}
            <Link href="/verify-email" className="text-foreground underline-offset-4 hover:underline">
              Open verification
            </Link>
          </p>
        ) : null}

        {canWrite ? (
          <form onSubmit={onSubmit} className="surface mt-6 space-y-4 p-5">
            <label className="block">
              <span className="label-caps">Ticker</span>
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="mt-2 w-full border border-white/[0.1] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.22]"
              >
                {TRACKED_SYMBOLS.map((sym) => (
                  <option key={sym} value={sym} className="bg-background text-foreground">
                    {sym}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label-caps">Post</span>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                maxLength={2000}
                rows={4}
                placeholder="Share a thesis, question, or note…"
                className="mt-2 w-full resize-y border border-white/[0.1] bg-transparent px-3 py-2 text-sm outline-none focus:border-white/[0.22]"
              />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-[10px] text-muted-foreground">
                {body.length}/2000
              </span>
              <button
                type="submit"
                disabled={postMutation.isPending || !body.trim()}
                className="border border-white/[0.12] px-3 py-2 font-mono text-xs uppercase tracking-wide hover:bg-white/[0.06] disabled:opacity-50"
              >
                {postMutation.isPending ? "Posting…" : "Post"}
              </button>
            </div>
            {error ? <p className="text-sm text-bearish">{error}</p> : null}
          </form>
        ) : null}

        <div className="surface mt-6 space-y-4 p-5">
          <h2 className="label-caps">Feed</h2>
          {feedQuery.isLoading ? (
            <p className="font-mono text-xs text-muted-foreground">Loading feed…</p>
          ) : null}
          {feedQuery.isError ? (
            <p className="text-sm text-bearish">Could not load feed.</p>
          ) : null}
          {!feedQuery.isLoading && posts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No posts yet.</p>
          ) : null}
          {posts.map((post) => (
            <SocialPostCard
              key={post.id}
              post={post}
              onChanged={() => {
                void queryClient.invalidateQueries({ queryKey: ["social-feed"] });
              }}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
