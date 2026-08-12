"use client";

import { useEffect, useState } from "react";

import { useHomescreen } from "@/components/homescreen-provider";

const STORAGE_KEY = "se_homescreen_tip_dismissed_v1";

/**
 * Soft Install / Add to Home Screen coach — especially for iPhone Safari,
 * where there is no native install prompt.
 */
export function HomescreenInstallTip() {
  const { displayMode, isApple, isInstallable, promptInstall } = useHomescreen();
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (displayMode === "standalone") return;
    try {
      if (window.localStorage.getItem(STORAGE_KEY) === "1") return;
    } catch {
      /* ignore */
    }
    // Delay so first paint stays clean; only coach after a beat.
    const t = window.setTimeout(() => setVisible(true), 1800);
    return () => window.clearTimeout(t);
  }, [displayMode]);

  if (!visible || displayMode === "standalone") return null;

  async function onInstall() {
    setBusy(true);
    try {
      const ok = await promptInstall();
      if (ok) dismiss();
    } finally {
      setBusy(false);
    }
  }

  function dismiss() {
    setVisible(false);
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
  }

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex justify-center px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2"
      role="status"
    >
      <div className="pointer-events-auto surface w-full max-w-md overflow-hidden border-white/[0.1] bg-card/85 p-4 shadow-[0_-12px_40px_-20px_rgba(0,0,0,0.65)] backdrop-blur-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="label-caps text-muted-foreground/70">
              {isApple ? "iPhone · Home Screen" : "Install app"}
            </p>
            <p className="mt-1.5 text-sm leading-snug text-foreground/90">
              {isApple
                ? "Add Signal Engine to your Home Screen for full-bleed immersion — no Safari chrome, instant reopen."
                : "Install Signal Engine for an app-like shell: faster reopen, more screen, fewer tabs."}
            </p>
          </div>
          <button
            type="button"
            onClick={dismiss}
            className="shrink-0 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55 hover:text-muted-foreground"
            aria-label="Dismiss"
          >
            Close
          </button>
        </div>

        {isApple ? (
          <ol className="mt-3 space-y-1.5 font-mono text-[11px] leading-relaxed text-muted-foreground/80">
            <li>
              1. Tap <span className="text-foreground/85">Share</span>{" "}
              <span aria-hidden className="text-foreground/70">
                ⎙
              </span>
            </li>
            <li>
              2. Scroll and choose{" "}
              <span className="text-foreground/85">Add to Home Screen</span>
            </li>
            <li>
              3. Open the icon — status bar blends into the void
            </li>
          </ol>
        ) : (
          <div className="mt-3 flex flex-wrap gap-2">
            {isInstallable ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void onInstall()}
                className="border border-white/[0.12] bg-foreground/90 px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-background disabled:opacity-50"
              >
                {busy ? "Opening…" : "Install"}
              </button>
            ) : (
              <p className="font-mono text-[11px] text-muted-foreground/65">
                Use your browser menu → Install app / Add to Home screen.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
