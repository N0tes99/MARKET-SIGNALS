"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import {
  createTickerRequest,
  fetchMyTickerRequests,
  type TickerRequest,
} from "@/services/api";

export default function RequestTickerPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [symbol, setSymbol] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mine, setMine] = useState<TickerRequest[]>([]);

  const reload = useCallback(async () => {
    const rows = await fetchMyTickerRequests();
    setMine(rows);
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login?next=/request-ticker");
      return;
    }
    void reload().catch(() => undefined);
  }, [loading, user, router, reload]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      await createTickerRequest({
        symbol: symbol.trim(),
        message: message.trim(),
      });
      setSymbol("");
      setMessage("");
      setOk("Sent to admin. You’ll see status updates here.");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) {
    return (
      <main className="min-h-screen">
        <SiteHeader compact />
        <p className="p-8 font-mono text-[11px] text-muted-foreground/50">Loading…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Request ticker" />
      <div className="container mx-auto max-w-lg px-4 py-10">
        <p className="label-caps">Watchlist</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Request a ticker</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Ask admin to add a symbol to the tracked universe. Keep the note short — why
          it matters helps prioritization.
        </p>

        <form onSubmit={onSubmit} className="surface mt-8 space-y-4 p-5">
          <label className="block">
            <span className="label-caps">Symbol</span>
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="NVDA"
              required
              maxLength={16}
              className="mt-2 w-full border border-white/[0.1] bg-transparent px-3 py-2 font-mono text-sm uppercase outline-none focus:border-white/[0.22]"
            />
          </label>
          <label className="block">
            <span className="label-caps">Message to admin</span>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              maxLength={1000}
              placeholder="Why track this? Setup ideas, liquidity notes…"
              className="mt-2 w-full resize-y border border-white/[0.1] bg-transparent px-3 py-2 text-sm outline-none focus:border-white/[0.22]"
            />
          </label>
          {error ? <p className="text-sm text-bearish">{error}</p> : null}
          {ok ? <p className="text-sm text-bullish">{ok}</p> : null}
          <button
            type="submit"
            disabled={busy || !symbol.trim()}
            className="w-full border border-white/[0.12] px-3 py-2.5 font-mono text-xs uppercase tracking-wide transition-colors hover:bg-white/[0.06] disabled:opacity-50"
          >
            {busy ? "Sending…" : "Send request"}
          </button>
        </form>

        <div className="mt-10">
          <p className="label-caps text-muted-foreground/60">Your recent requests</p>
          {mine.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">None yet.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {mine.map((row) => (
                <li
                  key={row.id}
                  className="border border-white/[0.06] bg-card/10 px-3 py-3"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-mono text-sm">{row.symbol}</span>
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
                      {row.status}
                    </span>
                  </div>
                  {row.message ? (
                    <p className="mt-1 text-sm text-muted-foreground">{row.message}</p>
                  ) : null}
                  {row.admin_note ? (
                    <p className="mt-1 font-mono text-[11px] text-muted-foreground/70">
                      Admin: {row.admin_note}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        <p className="mt-8 text-sm text-muted-foreground">
          <Link href="/" className="underline-offset-4 hover:underline">
            Back to dashboard
          </Link>
        </p>
      </div>
    </main>
  );
}
