"use client";

import type { ReactNode } from "react";
import Link from "next/link";

import { AuthNav } from "@/components/auth-nav";
import { useAuth } from "@/components/auth-provider";
import { SignalEngineLogo } from "@/components/signal-engine-logo";

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
      className="font-mono text-[10px] tracking-widest text-muted-foreground/45 transition-colors hover:text-muted-foreground/70"
    >
      Built by Notes
    </a>
  );
}

function MainNav() {
  const { user } = useAuth();
  return (
    <nav className="flex flex-wrap items-center gap-x-3 gap-y-1 sm:gap-x-4 sm:gap-y-2">
      <Link
        href="/social"
        className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
      >
        Social
      </Link>
      {user ? (
        <Link
          href="/request-ticker"
          className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
        >
          Request
        </Link>
      ) : null}
      {user?.is_admin ? (
        <>
          <Link
            href="/admin/access"
            className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
          >
            Access
          </Link>
          <Link
            href="/admin/requests"
            className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
          >
            Requests
          </Link>
        </>
      ) : null}
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
      <header className="sticky top-0 z-40 border-b border-white/[0.05] bg-card/20 pt-[env(safe-area-inset-top)] backdrop-blur-xl supports-[backdrop-filter]:bg-card/15">
        <div className="container mx-auto flex items-center justify-between gap-4 px-4 py-3.5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <SignalEngineLogo size="sm" />
            <BuiltByNotes />
          </div>
          <MainNav />
        </div>
      </header>
    );
  }

  return (
    <header className="border-b border-white/[0.05] bg-card/18 pt-[env(safe-area-inset-top)] backdrop-blur-xl">
      <div className="container mx-auto flex flex-col gap-3 px-3 py-4 sm:flex-row sm:items-end sm:justify-between sm:gap-4 sm:px-4 sm:py-7 md:py-8">
        <div className="min-w-0 overflow-visible">
          <SignalEngineLogo size="lg" href={false} />
          <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 pl-[2.625rem] sm:mt-3 sm:pl-[3.75rem]">
            <p className="text-sm font-light tracking-wide text-muted-foreground/75 sm:text-base">
              {title}
            </p>
            <BuiltByNotes />
          </div>
        </div>
        <div className="flex min-w-0 flex-col items-start gap-2 sm:shrink-0 sm:items-end sm:pb-0.5">
          <MainNav />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {trailing}
            {subtitle ? <div className="opacity-80 sm:max-w-[16rem] sm:text-right">{subtitle}</div> : null}
          </div>
        </div>
      </div>
    </header>
  );
}
