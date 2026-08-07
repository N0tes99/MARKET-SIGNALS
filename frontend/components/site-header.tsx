"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { AuthNav } from "@/components/auth-nav";
import { useAuth } from "@/components/auth-provider";

interface SiteHeaderProps {
  /** Compact bar for non-home pages. */
  compact?: boolean;
  title?: string;
  subtitle?: ReactNode;
  trailing?: ReactNode;
}

function BuiltByNotes() {
  return (
    <a
      href="https://x.com/notesonchain"
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-[10px] tracking-widest text-muted-foreground/50 transition-colors hover:text-muted-foreground"
    >
      Built by Notes
    </a>
  );
}

function MainNav() {
  const { user } = useAuth();
  return (
    <nav className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <Link
        href="/social"
        className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
      >
        Social
      </Link>
      {user ? (
        <Link
          href="/favorites"
          className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
        >
          Favorites
        </Link>
      ) : null}
      <AuthNav />
    </nav>
  );
}

export function SiteHeader({
  compact = false,
  title = "Market intelligence",
  subtitle,
  trailing,
}: SiteHeaderProps) {
  if (compact) {
    return (
      <header className="border-b border-white/[0.06] bg-card/25 backdrop-blur-xl">
        <div className="container mx-auto flex items-center justify-between gap-4 px-4 py-3.5">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <Link href="/" className="group">
              <p className="label-caps transition-colors group-hover:text-foreground/90">
                Signal Engine
              </p>
            </Link>
            <BuiltByNotes />
          </div>
          <MainNav />
        </div>
      </header>
    );
  }

  return (
    <header className="border-b border-white/[0.06] bg-card/25 backdrop-blur-xl">
      <div className="container mx-auto flex items-end justify-between gap-4 px-4 py-7 sm:py-8">
        <div>
          <div className="mb-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <p className="label-caps">Signal Engine</p>
            <BuiltByNotes />
          </div>
          <h1 className="text-2xl font-light tracking-tight text-foreground">{title}</h1>
        </div>
        <div className="flex flex-col items-end gap-2.5 pb-0.5">
          <MainNav />
          {trailing}
          {subtitle ? (
            <div className="max-w-[16rem] text-right opacity-80">{subtitle}</div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
