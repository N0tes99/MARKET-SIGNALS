"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth-provider";
import { fetchGateStatus, type GateStatus } from "@/services/api";

const BYPASS = new Set([
  "/login",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
  "/unlock",
  "/pending",
]);

const REQUIRE_LOGIN = process.env.NEXT_PUBLIC_REQUIRE_LOGIN === "true";

function isGranted(status: GateStatus | undefined): boolean {
  return status?.next_step === "open" || status?.next_step === "dashboard";
}

/**
 * Production UI gate: waitlist → authenticator → dashboard.
 * Locally (REQUIRE_LOGIN unset) this is a pass-through so /chart can render
 * even when uvicorn is down or Windows `localhost` IPv6 hangs.
 * Gate status is cached so soft navigations do not blank the whole tree.
 */
export function ProductAccessGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const pathBypass = BYPASS.has(pathname);
  const bypass = !REQUIRE_LOGIN || pathBypass;

  const gateQuery = useQuery({
    queryKey: ["gate-status"],
    queryFn: fetchGateStatus,
    // Cookie session — do not wait for fetchMe (that doubled cold-start time).
    enabled: REQUIRE_LOGIN && !pathBypass,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  useEffect(() => {
    if (!REQUIRE_LOGIN || pathBypass) return;
    const status = gateQuery.data;
    if (isGranted(status)) return;
    if (!status) {
      if (!loading && !gateQuery.isLoading && !user) {
        router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      }
      return;
    }
    if (status.next_step === "login") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (status.next_step === "pending") {
      router.replace("/pending");
      return;
    }
    if (status.next_step === "mfa" || status.next_step === "enroll") {
      router.replace(`/unlock?next=${encodeURIComponent(pathname)}`);
    }
  }, [pathBypass, loading, user, gateQuery.data, gateQuery.isLoading, pathname, router]);

  if (bypass) {
    return <>{children}</>;
  }

  if (isGranted(gateQuery.data)) {
    return <>{children}</>;
  }

  if ((loading && !gateQuery.data) || (gateQuery.isLoading && !gateQuery.data)) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2">
        <p className="font-mono text-[11px] text-muted-foreground/50">Connecting…</p>
        <p className="font-mono text-[10px] text-muted-foreground/40">
          API may still be waking up
        </p>
      </div>
    );
  }

  if (gateQuery.isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-4">
        <p className="font-mono text-[11px] text-muted-foreground/50">
          Access check failed — API may still be warming up
        </p>
        <button
          type="button"
          className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:underline"
          onClick={() => void gateQuery.refetch()}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="font-mono text-[11px] text-muted-foreground/50">Connecting…</p>
    </div>
  );
}
