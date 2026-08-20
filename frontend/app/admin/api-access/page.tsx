"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AdminNav } from "@/components/admin-nav";
import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import {
  createAdminApiKey,
  fetchAdminApiKeys,
  fetchApiKeyScopes,
  revokeAdminApiKey,
  type ApiKeyCreated,
  type ApiKeyRecord,
} from "@/services/api";

export default function AdminApiAccessPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [apiKeys, setApiKeys] = useState<ApiKeyRecord[]>([]);
  const [apiScopes, setApiScopes] = useState<string[]>([]);
  const [keyUsername, setKeyUsername] = useState("");
  const [keyName, setKeyName] = useState("");
  const [keyScopes, setKeyScopes] = useState<string[]>(["expansion:read", "cortex:read"]);
  const [keyExpiresAt, setKeyExpiresAt] = useState("");
  const [issuedSecret, setIssuedSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const [keys, scopes] = await Promise.all([fetchAdminApiKeys(), fetchApiKeyScopes()]);
    setApiKeys(keys);
    setApiScopes(scopes.filter((s) => s !== "*:read"));
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user?.is_admin) {
      router.replace("/");
      return;
    }
    void reload().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load API keys"),
    );
  }, [loading, user, router, reload]);

  function toggleKeyScope(scope: string) {
    setKeyScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope],
    );
  }

  async function onCreateKey(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setIssuedSecret(null);
    try {
      const created: ApiKeyCreated = await createAdminApiKey({
        username: keyUsername.trim(),
        name: keyName.trim(),
        scopes: keyScopes,
        expires_at: keyExpiresAt ? new Date(keyExpiresAt).toISOString() : null,
      });
      setIssuedSecret(created.secret);
      setKeyName("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "API key issue failed");
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
      <SiteHeader compact title="API access" />
      <div className="container mx-auto max-w-3xl px-4 py-10">
        <p className="label-caps">Admin</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Builder API keys</h1>
        <p className="mt-2 text-sm text-muted-foreground/75">
          Issue keys only to users with an active{" "}
          <Link href="/admin/access" className="underline-offset-2 hover:underline">
            dashboard grant
          </Link>
          . Keys bypass TOTP for programmatic access.
        </p>

        <AdminNav />

        <div className="surface mt-6 p-5">
          <p className="text-sm text-muted-foreground/70">
            Headers:{" "}
            <span className="font-mono text-foreground/80">Authorization: Bearer se_live_…</span>{" "}
            or <span className="font-mono text-foreground/80">X-API-Key</span>
          </p>

          <form onSubmit={onCreateKey} className="mt-5 grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="label-caps text-muted-foreground/55">Username</span>
              <input
                value={keyUsername}
                onChange={(e) => setKeyUsername(e.target.value)}
                className="mt-2 w-full border border-white/[0.08] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.18]"
                required
              />
            </label>
            <label className="block">
              <span className="label-caps text-muted-foreground/55">Label</span>
              <input
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="discord bot"
                className="mt-2 w-full border border-white/[0.08] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.18]"
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="label-caps text-muted-foreground/55">Expires (optional)</span>
              <input
                type="datetime-local"
                value={keyExpiresAt}
                onChange={(e) => setKeyExpiresAt(e.target.value)}
                className="mt-2 w-full border border-white/[0.08] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.18]"
              />
            </label>
            <div className="sm:col-span-2">
              <span className="label-caps text-muted-foreground/55">Scopes (read-only)</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {apiScopes.map((scope) => (
                  <button
                    key={scope}
                    type="button"
                    onClick={() => toggleKeyScope(scope)}
                    className={`border px-2 py-1 font-mono text-[10px] uppercase tracking-widest ${
                      keyScopes.includes(scope)
                        ? "border-foreground/30 bg-foreground/10 text-foreground/90"
                        : "border-white/[0.08] text-muted-foreground/60"
                    }`}
                  >
                    {scope}
                  </button>
                ))}
              </div>
            </div>
            {error ? (
              <p className="font-mono text-[11px] text-bearish/80 sm:col-span-2">{error}</p>
            ) : null}
            <button
              type="submit"
              disabled={busy || keyScopes.length === 0}
              className="sm:col-span-2 border border-white/[0.1] bg-foreground/90 py-2.5 font-mono text-[11px] uppercase tracking-widest text-background disabled:opacity-40"
            >
              {busy ? "Issuing…" : "Issue API key"}
            </button>
          </form>

          {issuedSecret ? (
            <div className="mt-4 border border-amber-500/30 bg-amber-500/10 p-4">
              <p className="label-caps text-amber-400/90">Copy now — shown once</p>
              <p className="mt-2 break-all font-mono text-xs text-foreground/90">{issuedSecret}</p>
            </div>
          ) : null}

          <ul className="mt-6 divide-y divide-white/[0.05]">
            {apiKeys.length === 0 ? (
              <li className="py-3 font-mono text-[11px] text-muted-foreground/45">No API keys yet</li>
            ) : (
              apiKeys.map((k) => (
                <li key={k.id} className="flex flex-wrap items-baseline justify-between gap-3 py-3">
                  <div>
                    <p className="font-mono text-sm text-foreground/90">
                      @{k.username}
                      {k.name ? ` · ${k.name}` : ""}
                    </p>
                    <p className="mt-1 font-mono text-[10px] text-muted-foreground/50">
                      {k.key_prefix}… · {k.scopes.join(", ")} ·{" "}
                      {k.active ? "active" : "revoked/expired"}
                      {k.last_used_at
                        ? ` · used ${new Date(k.last_used_at).toLocaleString()}`
                        : ""}
                    </p>
                  </div>
                  {k.active ? (
                    <button
                      type="button"
                      className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
                      onClick={() =>
                        void revokeAdminApiKey(k.id)
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
      </div>
    </main>
  );
}
