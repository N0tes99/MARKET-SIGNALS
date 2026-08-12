"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import {
  createAccessGrant,
  fetchAccessGrants,
  fetchAccessHealth,
  fetchWaitlistUsers,
  revokeAccessGrant,
  sendAlertTest,
  type AccessGrant,
  type AccessHealth,
  type WaitlistUser,
} from "@/services/api";

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AdminAccessPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [grants, setGrants] = useState<AccessGrant[]>([]);
  const [waitlist, setWaitlist] = useState<WaitlistUser[]>([]);
  const [username, setUsername] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<AccessHealth | null>(null);
  const [discordNote, setDiscordNote] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const [rows, waiting, env] = await Promise.all([
      fetchAccessGrants(),
      fetchWaitlistUsers(),
      fetchAccessHealth(),
    ]);
    setGrants(rows);
    setWaitlist(waiting);
    setHealth(env);
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

  function setPresetDays(days: number) {
    const d = new Date();
    d.setDate(d.getDate() + days);
    setExpiresAt(toLocalInput(d));
  }

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
          Grant by username. After you grant, they sign in and set up a{" "}
          <span className="text-foreground/85">personal</span> authenticator (shown once),
          then unlock with that app&apos;s 6-digit code about every 12 hours. Tell them to
          hit Refresh on the waitlist — it now sends them to unlock.{" "}
          <Link href="/admin/wallets" className="underline-offset-2 hover:underline">
            Wallets
          </Link>
          {" · "}
          <Link href="/admin/requests" className="underline-offset-2 hover:underline">
            Ticker requests
          </Link>
          {" · "}
          <Link href="/unlock" className="underline-offset-2 hover:underline">
            Unlock
          </Link>
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            {health?.strip ?? "env…"}
          </p>
          <button
            type="button"
            className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline disabled:opacity-40"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              setDiscordNote(null);
              void sendAlertTest("discord")
                .then((r) =>
                  setDiscordNote(
                    r.discord === true ? "Discord test sent" : "Discord not configured",
                  ),
                )
                .catch((err) =>
                  setError(err instanceof Error ? err.message : "Discord test failed"),
                )
                .finally(() => setBusy(false));
            }}
          >
            Test Discord
          </button>
          {discordNote ? (
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
              {discordNote}
            </p>
          ) : null}
        </div>

        {waitlist.length > 0 ? (
          <div className="surface mt-8 p-5">
            <p className="label-caps text-muted-foreground/55">Waiting ({waitlist.length})</p>
            <ul className="mt-3 divide-y divide-white/[0.05]">
              {waitlist.map((w) => (
                <li key={w.id} className="flex flex-wrap items-baseline justify-between gap-3 py-2.5">
                  <div>
                    <p className="font-mono text-sm text-foreground/90">@{w.username}</p>
                    <p className="font-mono text-[10px] text-muted-foreground/50">
                      {w.email}
                      {w.email_verified ? "" : " · email unverified"} · joined{" "}
                      {new Date(w.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
                    onClick={() => {
                      setUsername(w.username);
                      if (!expiresAt) setPresetDays(30);
                    }}
                  >
                    Fill grant
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="mt-8 font-mono text-[11px] text-muted-foreground/45">
            Waitlist empty — no users without an active grant.
          </p>
        )}

        <form onSubmit={onCreate} className="surface mt-6 grid gap-3 p-5 sm:grid-cols-2">
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
            <div className="mt-2 flex flex-wrap gap-3">
              <button
                type="button"
                className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70 underline-offset-2 hover:underline"
                onClick={() => setPresetDays(7)}
              >
                7 days
              </button>
              <button
                type="button"
                className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70 underline-offset-2 hover:underline"
                onClick={() => setPresetDays(30)}
              >
                30 days
              </button>
            </div>
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
          {error ? (
            <p className="font-mono text-[11px] text-bearish/80 sm:col-span-2">
              {error}{" "}
              <Link href="/unlock" className="underline-offset-2 hover:underline">
                Unlock
              </Link>
            </p>
          ) : null}
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
