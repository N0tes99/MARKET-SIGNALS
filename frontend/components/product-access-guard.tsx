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
    queryKey: ["gate-status", user?.id ?? "anon"],
    queryFn: fetchGateStatus,
    enabled: REQUIRE_LOGIN && !pathBypass && !loading && Boolean(user),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  useEffect(() => {
    if (!REQUIRE_LOGIN || pathBypass || loading) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    const status = gateQuery.data;
    if (!status) return;
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
  }, [pathBypass, loading, user, gateQuery.data, pathname, router]);

  if (bypass) {
    return <>{children}</>;
  }

  if (isGranted(gateQuery.data)) {
    return <>{children}</>;
  }

  if (loading || !user || gateQuery.isLoading || gateQuery.isFetching) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-[11px] text-muted-foreground/50">Loading…</p>
      </div>
    );
  }

  if (gateQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-[11px] text-muted-foreground/50">Access check failed</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="font-mono text-[11px] text-muted-foreground/50">Loading…</p>
    </div>
  );
}
