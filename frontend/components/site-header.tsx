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

function MainNav() {
  const { user } = useAuth();
  return (
    <nav className="flex flex-wrap items-center gap-3">
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
        <div className="container mx-auto flex items-center justify-between gap-4 px-4 py-4">
          <Link href="/" className="group">
            <p className="label-caps transition-colors group-hover:text-foreground">
              Signal Engine
            </p>
          </Link>
          <MainNav />
        </div>
      </header>
    );
  }

  return (
    <header className="border-b border-white/[0.06] bg-card/25 backdrop-blur-xl">
      <div className="container mx-auto flex items-end justify-between gap-4 px-4 py-8">
        <div>
          <p className="label-caps mb-3">Signal Engine</p>
          <h1 className="text-2xl font-light tracking-tight text-foreground">{title}</h1>
        </div>
        <div className="flex flex-col items-end gap-2 pb-1">
          <MainNav />
          {trailing}
          {subtitle}
        </div>
      </div>
    </header>
  );
}
