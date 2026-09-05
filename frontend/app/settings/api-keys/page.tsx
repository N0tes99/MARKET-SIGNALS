"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import {
  fetchMyApiKeys,
  revokeMyApiKey,
  type ApiKeyRecord,
} from "@/services/api";

export default function MyApiKeysPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const rows = await fetchMyApiKeys();
    setKeys(rows);
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login?next=/settings/api-keys");
      return;
    }
    void reload().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load keys"),
    );
  }, [loading, user, router, reload]);

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
      <SiteHeader compact title="API keys" />
      <div className="container mx-auto max-w-2xl px-4 py-10">
        <p className="label-caps">Settings</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Your API keys</h1>
        <p className="mt-2 text-sm text-muted-foreground/75">
          Keys are issued by an admin. Treat a leaked{" "}
          <span className="font-mono text-foreground/85">se_live_…</span> key as a password —
          they skip TOTP, expire automatically, and cannot hit Radar backtest or Expansion
          replay. Use{" "}
          <span className="font-mono text-foreground/85">Authorization: Bearer se_live_…</span>.
        </p>

        {error ? (
          <p className="mt-4 font-mono text-[11px] text-bearish/80">{error}</p>
        ) : null}

        <ul className="mt-8 divide-y divide-white/[0.05]">
          {keys.length === 0 ? (
            <li className="py-4 font-mono text-[11px] text-muted-foreground/45">
              No keys issued yet — ask an admin on{" "}
              <Link href="/pending" className="underline-offset-2 hover:underline">
                pending
              </Link>
              .
            </li>
          ) : (
            keys.map((k) => (
              <li key={k.id} className="flex flex-wrap items-baseline justify-between gap-3 py-4">
                <div>
                  <p className="font-mono text-sm text-foreground/90">
                    {k.name || "API key"} · {k.key_prefix}…
                  </p>
                    <p className="mt-1 font-mono text-[10px] text-muted-foreground/50">
                      {k.scopes.join(", ")} · {k.active ? "active" : "revoked/expired"}
                      {k.expires_at
                        ? ` · expires ${new Date(k.expires_at).toLocaleDateString()}`
                        : ""}
                    </p>
                </div>
                {k.active ? (
                  <button
                    type="button"
                    className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
                    onClick={() =>
                      void revokeMyApiKey(k.id)
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
