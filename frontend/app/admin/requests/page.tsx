"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import {
  fetchAdminTickerRequests,
  resolveTickerRequest,
  type TickerRequest,
} from "@/services/api";

export default function AdminTickerRequestsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [rows, setRows] = useState<TickerRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"open" | "all">("open");

  const reload = useCallback(async () => {
    const data = await fetchAdminTickerRequests(filter === "open" ? "open" : undefined);
    setRows(data);
  }, [filter]);

  useEffect(() => {
    if (loading) return;
    if (!user?.is_admin) {
      router.replace("/");
      return;
    }
    void reload().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load"),
    );
  }, [loading, user, router, reload]);

  async function resolve(id: string, status: "done" | "dismissed") {
    setError(null);
    try {
      await resolveTickerRequest(id, { status });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
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
      <SiteHeader compact title="Ticker requests" />
      <div className="container mx-auto max-w-3xl px-4 py-10">
        <p className="label-caps">Admin</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Ticker requests</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Messages from users asking to track a symbol.{" "}
          <Link href="/admin/access" className="underline-offset-2 hover:underline">
            Access grants
          </Link>
          {" · "}
          <Link href="/admin/wallets" className="underline-offset-2 hover:underline">
            Wallets
          </Link>
        </p>

        <div className="mt-6 flex gap-2">
          {(["open", "all"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              data-active={filter === f}
              className="seg-control-btn border border-white/[0.08] data-[active=true]:bg-white/[0.1] data-[active=true]:text-foreground"
            >
              {f}
            </button>
          ))}
        </div>

        {error ? <p className="mt-4 font-mono text-[11px] text-bearish/80">{error}</p> : null}

        <ul className="mt-6 space-y-3">
          {rows.length === 0 ? (
            <li className="text-sm text-muted-foreground">No requests.</li>
          ) : (
            rows.map((row) => (
              <li key={row.id} className="surface p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-mono text-lg tracking-tight">{row.symbol}</p>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
                    {row.status} · @{row.username}
                  </p>
                </div>
                {row.message ? (
                  <p className="mt-2 text-sm text-muted-foreground">{row.message}</p>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground/50">No message</p>
                )}
                <p className="mt-2 font-mono text-[10px] text-muted-foreground/45">
                  {new Date(row.created_at).toLocaleString()}
                </p>
                {row.status === "open" ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void resolve(row.id, "done")}
                      className="border border-white/[0.12] px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest hover:bg-white/[0.06]"
                    >
                      Mark done
                    </button>
                    <button
                      type="button"
                      onClick={() => void resolve(row.id, "dismissed")}
                      className="border border-white/[0.08] px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:bg-white/[0.04]"
                    >
                      Dismiss
                    </button>
                  </div>
                ) : null}
              </li>
            ))
          )}
        </ul>
      </div>
    </main>
  );
}
