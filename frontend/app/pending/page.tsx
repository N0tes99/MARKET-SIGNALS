"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { SignalEngineLogo } from "@/components/signal-engine-logo";
import { fetchGateStatus, type GateStatus } from "@/services/api";

export default function PendingPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [status, setStatus] = useState<GateStatus | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login?next=/pending");
      return;
    }
    let cancelled = false;
    (async () => {
      const s = await fetchGateStatus();
      if (cancelled) return;
      setStatus(s);
      if (s.next_step === "mfa" || s.next_step === "enroll") {
        router.replace("/unlock");
      } else if (s.next_step === "dashboard" || s.next_step === "open") {
        router.replace("/");
      }
    })().catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [loading, user, router]);

  return (
    <main className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 pt-[env(safe-area-inset-top)]">
      <div className="w-full max-w-md">
        <SignalEngineLogo size="lg" href={false} />
        <p className="mt-6 label-caps text-muted-foreground/70">Waitlist</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Access pending</h1>
        <p className="mt-2 text-sm text-muted-foreground/75">
          Thanks {user?.username ? `@${user.username}` : ""}. Your account is ready —
          access is still waiting on an admin grant.
        </p>
        <div className="surface mt-6 space-y-3 p-4">
          <p className="label-caps text-muted-foreground/60">What happens next</p>
          <ol className="list-decimal space-y-2 pl-4 text-sm text-muted-foreground/80">
            <li>An admin grants your username and sets how long access lasts.</li>
            <li>
              First unlock only: save your personal setup key in an authenticator
              app (Google Authenticator, Authy, etc.). Don&apos;t discard it — the
              same entry is how you get back in later.
            </li>
            <li>
              Each time your session resets (about every 12 hours), open that app
              and enter the current 6-digit code to unlock again.
            </li>
          </ol>
          <p className="font-mono text-[10px] text-muted-foreground/45">
            Use Refresh after you&apos;re approved — you&apos;ll be sent to unlock
            automatically.
          </p>
        </div>
        <p className="mt-6 font-mono text-[10px] text-muted-foreground/45">
          Status: {status?.next_step ?? "checking…"}
          {status?.enabled === false ? " · gate off (dev)" : ""}
        </p>
        <div className="mt-8 flex flex-wrap gap-4">
          <button
            type="button"
            className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => void fetchGateStatus().then(setStatus)}
          >
            Refresh
          </button>
          <Link
            href="/login"
            className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
            onClick={(e) => {
              e.preventDefault();
              void logout().then(() => router.push("/login"));
            }}
          >
            Sign out
          </Link>
        </div>
      </div>
    </main>
  );
}
