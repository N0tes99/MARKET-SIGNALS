"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AdminNav } from "@/components/admin-nav";
import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import {
  createAccessGrant,
  fetchAccessWallets,
  revokeAccessGrant,
  type WalletAccessUser,
} from "@/services/api";

function grantIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

export default function AdminWalletsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [rows, setRows] = useState<WalletAccessUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setRows(await fetchAccessWallets());
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user?.is_admin) {
      router.replace("/");
      return;
    }
    void reload().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load wallets"),
    );
  }, [loading, user, router, reload]);

  async function allow(row: WalletAccessUser, days: number) {
    setBusy(`${row.user_id}:${days}`);
    setError(null);
    try {
      await createAccessGrant({
        username: row.username,
        expires_at: grantIso(days),
        notes: `wallet ${row.chain} · ${days}d`,
      });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Grant failed");
    } finally {
      setBusy(null);
    }
  }

  async function revoke(row: WalletAccessUser) {
    if (!row.grant_id) return;
    setBusy(row.grant_id);
    setError(null);
    try {
      await revokeAccessGrant(row.grant_id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Revoke failed");
    } finally {
      setBusy(null);
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
      <SiteHeader compact title="Wallet access" />
      <div className="container mx-auto max-w-3xl px-4 py-10">
        <p className="label-caps">Admin</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Wallet users</h1>
        <p className="mt-2 text-sm text-muted-foreground/75">
          Handles are random and do not echo the address. Only this tab shows the
          wallet. Allow + duration works the same as email users.{" "}
          <Link href="/admin/access" className="underline-offset-2 hover:underline">
            Access
          </Link>
        </p>

        <AdminNav />

        {error ? (
          <p className="mt-6 font-mono text-[11px] text-bearish/80">{error}</p>
        ) : null}

        <ul className="mt-8 divide-y divide-white/[0.05]">
          {rows.length === 0 ? (
            <li className="py-4 font-mono text-[11px] text-muted-foreground/45">
              No wallet sign-ins yet
            </li>
          ) : (
            rows.map((row) => (
              <li
                key={`${row.chain}:${row.address}`}
                className="flex flex-wrap items-baseline justify-between gap-3 py-4"
              >
                <div className="min-w-0">
                  <p className="font-mono text-sm text-foreground/90">@{row.username}</p>
                  <p className="mt-1 break-all font-mono text-[10px] text-muted-foreground/50">
                    {row.chain} · {row.address}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground/45">
                    joined {new Date(row.created_at).toLocaleDateString()}
                    {row.granted && row.grant_expires_at
                      ? ` · allowed until ${new Date(row.grant_expires_at).toLocaleString()}`
                      : " · waiting"}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {row.granted ? (
                    <button
                      type="button"
                      disabled={busy !== null}
                      className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline disabled:opacity-40"
                      onClick={() => void revoke(row)}
                    >
                      Revoke
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={busy !== null}
                        className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline disabled:opacity-40"
                        onClick={() => void allow(row, 7)}
                      >
                        Allow 7d
                      </button>
                      <button
                        type="button"
                        disabled={busy !== null}
                        className="font-mono text-[10px] uppercase tracking-widest text-foreground/85 underline-offset-2 hover:underline disabled:opacity-40"
                        onClick={() => void allow(row, 30)}
                      >
                        Allow 30d
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))
          )}
        </ul>
      </div>
    </main>
  );
}
