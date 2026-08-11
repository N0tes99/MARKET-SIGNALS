"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import {
  createAccessGrant,
  fetchAccessGrants,
  revokeAccessGrant,
  type AccessGrant,
} from "@/services/api";

export default function AdminAccessPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [grants, setGrants] = useState<AccessGrant[]>([]);
  const [username, setUsername] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const rows = await fetchAccessGrants();
    setGrants(rows);
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user?.is_admin) {
      router.replace("/");
      return;
    }
    void reload().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load grants"),
    );
  }, [loading, user, router, reload]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createAccessGrant({
        username: username.trim(),
        expires_at: new Date(expiresAt).toISOString(),
        notes: notes.trim(),
      });
      setUsername("");
      setNotes("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Grant failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user?.is_admin) {
    return (
      <main className="min-h-screen">
        <SiteHeader compact />
        <p className="p-8 font-mono text-[11px] text-muted-foreground/50">Loading…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Access control" />
      <div className="container mx-auto max-w-3xl px-4 py-10">
        <p className="label-caps">Admin</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Who can unlock</h1>
        <p className="mt-2 text-sm text-muted-foreground/75">
          Grant access by username and expiry. After you grant, they sign in, enter your
          shared authenticator code, then reach the dashboard.{" "}
          <Link href="/unlock" className="underline-offset-2 hover:underline">
            Unlock
          </Link>
        </p>

        <form onSubmit={onCreate} className="surface mt-8 grid gap-3 p-5 sm:grid-cols-2">
          <label className="block sm:col-span-1">
            <span className="label-caps text-muted-foreground/55">Username</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-2 w-full border border-white/[0.08] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.18]"
              required
            />
          </label>
          <label className="block sm:col-span-1">
            <span className="label-caps text-muted-foreground/55">Expires</span>
            <input
              type="datetime-local"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="mt-2 w-full border border-white/[0.08] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.18]"
              required
            />
          </label>
          <label className="block sm:col-span-2">
            <span className="label-caps text-muted-foreground/55">Notes</span>
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="mt-2 w-full border border-white/[0.08] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.18]"
              placeholder="friend trial · 30d"
            />
          </label>
          {error ? <p className="font-mono text-[11px] text-bearish/80 sm:col-span-2">{error}</p> : null}
          <button
            type="submit"
            disabled={busy}
            className="sm:col-span-2 border border-white/[0.1] bg-foreground/90 py-2.5 font-mono text-[11px] uppercase tracking-widest text-background disabled:opacity-40"
          >
            {busy ? "Saving…" : "Grant access"}
          </button>
        </form>

        <ul className="mt-8 divide-y divide-white/[0.05]">
          {grants.length === 0 ? (
            <li className="py-4 font-mono text-[11px] text-muted-foreground/45">No grants yet</li>
          ) : (
            grants.map((g) => (
              <li key={g.id} className="flex flex-wrap items-baseline justify-between gap-3 py-4">
                <div>
                  <p className="font-mono text-sm text-foreground/90">@{g.username}</p>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground/50">
                    {g.email} · expires {new Date(g.expires_at).toLocaleString()} ·{" "}
                    {g.active ? "active" : "revoked/expired"}
                    {g.notes ? ` · ${g.notes}` : ""}
                  </p>
                </div>
                {g.active ? (
                  <button
                    type="button"
                    className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
                    onClick={() =>
                      void revokeAccessGrant(g.id)
                        .then(reload)
                        .catch((err) =>
                          setError(err instanceof Error ? err.message : "Revoke failed"),
                        )
                    }
                  >
                    Revoke
                  </button>
                ) : null}
              </li>
            ))
          )}
        </ul>
      </div>
    </main>
  );
}
