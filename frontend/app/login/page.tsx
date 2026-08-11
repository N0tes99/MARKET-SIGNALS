"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { PasswordInput } from "@/components/password-input";
import { SiteHeader } from "@/components/site-header";
import type { WalletChain } from "@/lib/ethereum-wallet";

const WALLET_OPTIONS: { chain: WalletChain; label: string; hint: string }[] = [
  { chain: "ethereum", label: "Ethereum", hint: "Phantom" },
  { chain: "solana", label: "Solana", hint: "Phantom" },
  { chain: "sui", label: "Sui", hint: "Phantom" },
];

export default function LoginPage() {
  const router = useRouter();
  const { login, loginWithWallet, user, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [walletBusy, setWalletBusy] = useState<WalletChain | null>(null);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/unlock");
    }
  }, [loading, user, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      router.push("/unlock");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function onWallet(chain: WalletChain) {
    setError(null);
    setWalletBusy(chain);
    try {
      await loginWithWallet(chain);
      router.push("/unlock");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Wallet sign-in failed");
    } finally {
      setWalletBusy(null);
    }
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto max-w-md px-4 py-16">
        <p className="label-caps">Account</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Sign in</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Email and password, or continue with Phantom (Ethereum, Solana, or Sui).
          Wallets only sign a login message — never a transaction.
        </p>

        <form onSubmit={onSubmit} className="surface mt-8 space-y-4 p-5">
          <label className="block">
            <span className="label-caps">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-2 w-full border border-white/[0.1] bg-transparent px-3 py-2 text-sm outline-none focus:border-white/[0.22]"
            />
          </label>
          <label className="block">
            <div className="flex items-baseline justify-between gap-3">
              <span className="label-caps">Password</span>
              <Link
                href="/forgot-password"
                className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground underline-offset-4 hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <PasswordInput
              required
              autoComplete="current-password"
              value={password}
              onChange={setPassword}
            />
          </label>
          {error ? <p className="text-sm text-bearish">{error}</p> : null}
          <button
            type="submit"
            disabled={submitting || walletBusy !== null}
            className="w-full border border-white/[0.12] px-3 py-2.5 font-mono text-xs uppercase tracking-wide transition-colors hover:bg-white/[0.06] disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-white/[0.08]" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
            or wallet
          </span>
          <div className="h-px flex-1 bg-white/[0.08]" />
        </div>

        <div className="mt-6 grid gap-2">
          {WALLET_OPTIONS.map((opt) => (
            <button
              key={opt.chain}
              type="button"
              disabled={submitting || walletBusy !== null}
              onClick={() => void onWallet(opt.chain)}
              className="flex w-full items-center justify-between border border-white/[0.12] px-3 py-2.5 text-left transition-colors hover:bg-white/[0.06] disabled:opacity-50"
            >
              <span className="font-mono text-xs uppercase tracking-wide">
                {walletBusy === opt.chain ? "Waiting for wallet…" : `Continue with ${opt.label}`}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
                {opt.hint}
              </span>
            </button>
          ))}
        </div>

        <p className="mt-6 text-sm text-muted-foreground">
          No account?{" "}
          <Link href="/register" className="text-foreground underline-offset-4 hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}
