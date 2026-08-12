"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { fetchGateStatus } from "@/services/api";

const BYPASS = new Set([
  "/login",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
  "/unlock",
  "/pending",
  "/admin/access",
]);

/**
 * After login, route users through waitlist → authenticator → dashboard.
 */
export function ProductAccessGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (BYPASS.has(pathname)) {
      setReady(true);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const status = await fetchGateStatus();
        if (cancelled) return;
        if (status.next_step === "login") {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          return;
        }
        if (status.next_step === "pending") {
          router.replace("/pending");
          return;
        }
        if (status.next_step === "open" || status.next_step === "dashboard") {
          setReady(true);
          return;
        }
        if (status.next_step === "mfa" || status.next_step === "enroll") {
          router.replace(`/unlock?next=${encodeURIComponent(pathname)}`);
          return;
        }
        setReady(true);
      } catch {
        if (!cancelled) setReady(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loading, user, pathname, router]);

  if (BYPASS.has(pathname)) {
    return <>{children}</>;
  }

  if (loading || !ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-[11px] text-muted-foreground/50">Loading…</p>
      </div>
    );
  }

  return <>{children}</>;
}
