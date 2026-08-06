"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import { fetchPublicProfile, followUser, unfollowUser } from "@/services/api";

export default function UserProfilePage() {
  const params = useParams<{ username: string }>();
  const username = decodeURIComponent(params.username ?? "");
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const profileQuery = useQuery({
    queryKey: ["profile", username],
    queryFn: () => fetchPublicProfile(username),
    enabled: Boolean(username),
  });

  const profile = profileQuery.data;
  const canFollow =
    Boolean(user?.email_verified) && profile && user && user.id !== profile.id;

  async function toggleFollow() {
    if (!profile || !canFollow) return;
    setPending(true);
    setError(null);
    try {
      if (profile.followed_by_me) {
        await unfollowUser(profile.id);
      } else {
        await followUser(profile.id);
      }
      await queryClient.invalidateQueries({ queryKey: ["profile", username] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Follow failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto max-w-lg px-4 py-10">
        <p className="label-caps">Profile</p>
        {profileQuery.isLoading ? (
          <p className="mt-4 font-mono text-xs text-muted-foreground">Loading…</p>
        ) : null}
        {profileQuery.isError ? (
          <p className="mt-4 text-sm text-bearish">User not found.</p>
        ) : null}
        {profile ? (
          <div className="surface mt-6 space-y-4 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="font-mono text-xl text-foreground">{profile.username}</h1>
                <p className="mt-2 font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                  {profile.post_count} posts · {profile.follower_count} followers ·{" "}
                  {profile.following_count} following
                </p>
              </div>
              {canFollow ? (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => void toggleFollow()}
                  className="border border-white/[0.12] px-3 py-2 font-mono text-xs uppercase tracking-wide hover:bg-white/[0.06] disabled:opacity-50"
                >
                  {profile.followed_by_me ? "Unfollow" : "Follow"}
                </button>
              ) : null}
            </div>
            {error ? <p className="text-sm text-bearish">{error}</p> : null}
            <Link
              href="/social"
              className="inline-block font-mono text-[11px] uppercase tracking-widest text-muted-foreground hover:text-foreground"
            >
              Back to Social
            </Link>
          </div>
        ) : null}
      </div>
    </main>
  );
}
