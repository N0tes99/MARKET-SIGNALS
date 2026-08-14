import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SignalEngineLogoProps {
  /** Compact = inner pages; full = home hero brand. */
  size?: "sm" | "lg";
  className?: string;
  /** Home link. Pass false when the parent already handles navigation. */
  href?: string | false;
  /**
   * Mark motion from logo_boot_holo sketch.
   * - boot: one-shot draw + caret, then idle flicker (dashboard hero)
   * - soft: brief settle (compact header)
   * - none: static
   */
  animation?: "boot" | "soft" | "none";
}

/**
 * Sharp-tech mark: mast + mitered broadcast wedges (not soft wifi arcs).
 * Scales as currentColor so it inherits the void palette.
 */
export function SignalMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className={cn("shrink-0 text-foreground", className)}
    >
      {/* outer wedge outline */}
      <path
        d="M20 3.5 L38 20.5 L33.6 24.2 L20 11.2 L6.4 24.2 L2 20.5 L20 3.5 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="miter"
        opacity="0.55"
      />
      {/* mid wedge fill */}
      <path
        d="M20 9 L32 20 L28.4 23.2 L20 14.6 L11.6 23.2 L8 20 L20 9 Z"
        fill="currentColor"
        fillOpacity="0.55"
      />
      {/* core peak */}
      <path d="M20 14 L25.4 22.5 H21.5 L20 19.8 L18.5 22.5 H14.6 L20 14 Z" fill="currentColor" />
      {/* mast */}
      <rect x="18.6" y="21.5" width="2.8" height="11.5" fill="currentColor" />
      {/* base plate */}
      <path d="M12 36 H28 L20 31.6 L12 36 Z" fill="currentColor" />
    </svg>
  );
}

function SignalHoloStage({
  mode,
  className,
  children,
}: {
  mode: "boot" | "soft" | "none";
  className?: string;
  children: ReactNode;
}) {
  if (mode === "none") {
    return <span className={cn("inline-flex shrink-0", className)}>{children}</span>;
  }

  return (
    <span className={cn("logo-holo-stage", className)} data-mode={mode}>
      {mode === "boot" ? (
        <>
          <span className="logo-holo-lines" aria-hidden />
          <span className="logo-holo-floor" aria-hidden />
          <span className="logo-holo-caret" aria-hidden />
        </>
      ) : null}
      <span className="logo-holo-mark">{children}</span>
    </span>
  );
}

export function SignalEngineLogo({
  size = "sm",
  className,
  href = "/",
  animation,
}: SignalEngineLogoProps) {
  const large = size === "lg";
  const motion = animation ?? (large ? "boot" : "soft");

  const mark = (
    <SignalHoloStage
      mode={motion}
      className={cn(
        "self-center overflow-visible",
        large ? "h-8 w-8 sm:h-11 sm:w-11" : "h-5 w-5",
      )}
    >
      <SignalMark className="h-full w-full" />
    </SignalHoloStage>
  );

  const word = (
    <span
      className={cn(
        "flex min-w-0 flex-col items-start font-brand font-semibold tracking-tight text-foreground sm:flex-row sm:flex-wrap sm:items-baseline sm:gap-x-2",
        // Space Grotesk — geometric title; Syne stays for ranks
        large
          ? "pb-[0.08em] pt-[0.04em] text-[1.7rem] leading-none sm:text-3xl sm:leading-[1.15] md:text-4xl"
          : "pb-[0.08em] text-sm leading-none",
      )}
    >
      <span className="whitespace-nowrap">Signal Engine</span>
      <span
        className={cn(
          "font-mono font-normal uppercase tracking-widest text-muted-foreground/45",
          large
            ? "sr-only text-[10px] sm:not-sr-only sm:inline sm:text-[11px]"
            : "sr-only text-[8px] sm:not-sr-only sm:inline",
        )}
      >
        (Not Financial Advice)
      </span>
    </span>
  );

  const rowClass = cn(
    "flex min-w-0 items-center overflow-visible text-foreground",
    large ? "gap-2.5 sm:gap-3.5" : "gap-2",
    className,
  );

  if (large) {
    // Home: real h1 so brand owns the document outline
    const heading = (
      <h1 className={rowClass}>
        {mark}
        {word}
      </h1>
    );
    if (href === false) return heading;
    return (
      <Link
        href={href}
        className="group block min-w-0 rounded-sm outline-none transition-opacity hover:opacity-90 focus-visible:ring-1 focus-visible:ring-white/25"
      >
        {heading}
      </Link>
    );
  }

  const compact = (
    <span className={rowClass}>
      {mark}
      {word}
    </span>
  );

  if (href === false) return compact;

  return (
    <Link
      href={href}
      className="group inline-flex rounded-sm outline-none transition-opacity hover:opacity-90 focus-visible:ring-1 focus-visible:ring-white/25"
    >
      {compact}
    </Link>
  );
}
