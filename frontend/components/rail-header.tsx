"use client";

import Link from "next/link";

export function RailHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-cyan-200/10 bg-[#05080c]/90 pt-[env(safe-area-inset-top)] backdrop-blur-md">
      <div className="container mx-auto flex h-14 items-center justify-between gap-4 px-4">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-cyan-200/55">
            Surface 6
          </p>
          <p className="truncate font-brand text-lg font-medium tracking-tight">Rail</p>
        </div>
        <nav className="flex shrink-0 items-center gap-4">
          <Link
            href="/perps"
            className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/60 hover:text-foreground"
          >
            Inspect on desk
          </Link>
          <Link
            href="/"
            className="font-mono text-[10px] uppercase tracking-widest text-cyan-100/80 hover:text-foreground"
          >
            ← Desk
          </Link>
        </nav>
      </div>
    </header>
  );
}
