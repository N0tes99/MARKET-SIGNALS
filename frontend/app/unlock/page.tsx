"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { SignalEngineLogo } from "@/components/signal-engine-logo";
import { fetchGateStatus, verifySiteGate } from "@/services/api";

function UnlockForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams?.get("next") || "/";
  const { user, loading: authLoading } = useAuth();

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchGateStatus();
        if (cancelled) return;
        if (status.next_step === "login") {
          router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
          return;
        }
        if (status.next_step === "pending") {
          router.replace("/pending");
          return;
        }
        if (status.next_step === "open" || status.next_step === "dashboard") {
          if (status.next_step === "open") {
            await verifySiteGate("");
          }
          router.replace(nextPath.startsWith("/") ? nextPath : "/");
          return;
        }
        // mfa
      } catch {
        if (!cancelled) setError("Could not reach unlock service");
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, nextPath, router, user]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await verifySiteGate(code.trim());
      router.replace(nextPath.startsWith("/") ? nextPath : "/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid code");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4">
      <div className="w-full max-w-md">
        <SignalEngineLogo size="lg" href={false} />
        <p className="mt-6 label-caps text-muted-foreground/70">Step 2 of 2</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight text-foreground">
          Authenticator code
        </h1>
        <p className="mt-2 text-sm text-muted-foreground/75">
          Your account is approved. Enter the 6-digit code from the shared Signal
          Engine authenticator to open the dashboard.
        </p>

        {checking || authLoading ? (
          <p className="mt-8 font-mono text-[11px] text-muted-foreground/50">Checking access…</p>
        ) : (
          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            <label className="block">
              <span className="label-caps text-muted-foreground/55">Code</span>
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]*"
                maxLength={8}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="mt-2 w-full border border-white/[0.08] bg-card/30 px-3 py-3 font-mono text-lg tracking-[0.35em] text-foreground outline-none backdrop-blur-sm placeholder:tracking-normal placeholder:text-muted-foreground/35 focus:border-white/[0.18]"
                placeholder="000000"
                autoFocus
              />
            </label>
            {error ? <p className="font-mono text-[11px] text-bearish/80">{error}</p> : null}
            <button
              type="submit"
              disabled={submitting || code.replace(/\D/g, "").length < 6}
              className="w-full border border-white/[0.1] bg-foreground/90 py-3 font-mono text-[11px] uppercase tracking-widest text-background transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {submitting ? "Verifying…" : "Enter dashboard"}
            </button>
            <p className="font-mono text-[10px] text-muted-foreground/45">
              Signed in as {user?.username ?? "…"} ·{" "}
              <Link href="/pending" className="underline-offset-2 hover:underline">
                waitlist status
              </Link>
            </p>
          </form>
        )}
      </div>
    </main>
  );
}

export default function UnlockPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center">
          <p className="font-mono text-[11px] text-muted-foreground/50">Loading…</p>
        </main>
      }
    >
      <UnlockForm />
    </Suspense>
  );
}
