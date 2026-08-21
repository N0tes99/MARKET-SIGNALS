"use client";

import { useEffect, useState, type ReactNode } from "react";

/**
 * Mount children after first paint / idle so the primary dashboard
 * (paper + rankings + quotes) can fetch without competing with heavy feeds.
 */
export function DeferredMount({
  children,
  delayMs = 0,
  fallback = null,
}: {
  children: ReactNode;
  /** Extra delay after idle (or timeout fallback). */
  delayMs?: number;
  fallback?: ReactNode;
}) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let idleId: number | undefined;

    const arm = () => {
      if (delayMs <= 0) {
        if (!cancelled) setReady(true);
        return;
      }
      timeoutId = setTimeout(() => {
        if (!cancelled) setReady(true);
      }, delayMs);
    };

    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      idleId = window.requestIdleCallback(() => arm(), { timeout: 1200 });
    } else {
      timeoutId = setTimeout(arm, 200);
    }

    return () => {
      cancelled = true;
      if (timeoutId != null) clearTimeout(timeoutId);
      if (idleId != null && typeof window !== "undefined" && "cancelIdleCallback" in window) {
        window.cancelIdleCallback(idleId);
      }
    };
  }, [delayMs]);

  if (!ready) return <>{fallback}</>;
  return <>{children}</>;
}
