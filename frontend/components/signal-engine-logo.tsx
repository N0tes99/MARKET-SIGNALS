import Link from "next/link";

import { cn } from "@/lib/utils";

interface SignalEngineLogoProps {
  /** Compact = inner pages; full = home hero brand. */
  size?: "sm" | "lg";
  className?: string;
  /** Home link. Pass false when the parent already handles navigation. */
  href?: string | false;
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

export function SignalEngineLogo({
  size = "sm",
  className,
  href = "/",
}: SignalEngineLogoProps) {
  const large = size === "lg";

  const mark = (
    <SignalMark
      className={cn(
        "self-center overflow-visible",
        large ? "h-10 w-10 sm:h-11 sm:w-11" : "h-5 w-5",
      )}
    />
  );

  const word = (
    <span
      className={cn(
        "inline-flex flex-wrap items-baseline gap-x-2 whitespace-nowrap font-brand font-semibold tracking-tight text-foreground",
        // Space Grotesk — geometric title; Syne stays for ranks
        large
          ? "pb-[0.12em] pt-[0.04em] text-3xl leading-[1.2] sm:text-4xl"
          : "pb-[0.08em] text-sm leading-[1.2]",
      )}
    >
      Signal Engine
      <span
        className={cn(
          "font-mono font-normal uppercase tracking-widest text-muted-foreground/45",
          large ? "text-[10px] sm:text-[11px]" : "text-[8px]",
        )}
      >
        (Not Financial Advice)
      </span>
    </span>
  );

  const rowClass = cn(
    "inline-flex items-center overflow-visible text-foreground",
    large ? "gap-3.5" : "gap-2",
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
        className="group block rounded-sm outline-none transition-opacity hover:opacity-90 focus-visible:ring-1 focus-visible:ring-white/25"
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
