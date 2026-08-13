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
  "/admin/access",
  "/admin/requests",
]);

function isGranted(status: GateStatus | undefined): boolean {
  return status?.next_step === "open" || status?.next_step === "dashboard";
}

/**
 * After login, route users through waitlist → authenticator → dashboard.
 * Caches gate status so soft navigations do not blank the whole tree.
 */
export function ProductAccessGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const bypass = BYPASS.has(pathname);

  const gateQuery = useQuery({
    queryKey: ["gate-status", user?.id ?? "anon"],
    queryFn: fetchGateStatus,
    enabled: !loading && !bypass,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  useEffect(() => {
    if (loading || bypass || !gateQuery.data) return;
    const status = gateQuery.data;
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
  }, [loading, bypass, gateQuery.data, pathname, router]);

  if (bypass) {
    return <>{children}</>;
  }

  // Keep prior grant visible while revalidating — avoids full-page Loading flash.
  if (isGranted(gateQuery.data)) {
    return <>{children}</>;
  }

  if (loading || gateQuery.isLoading || gateQuery.isFetching) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-[11px] text-muted-foreground/50">Loading…</p>
      </div>
    );
  }

  // Error / unexpected: fail open so the app remains usable.
  if (gateQuery.isError) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="font-mono text-[11px] text-muted-foreground/50">Loading…</p>
    </div>
  );
}
