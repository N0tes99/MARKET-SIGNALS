"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { AuthNav } from "@/components/auth-nav";
import { useAuth } from "@/components/auth-provider";
import { SignalEngineLogo } from "@/components/signal-engine-logo";
import { cn } from "@/lib/utils";

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

function NavLink({ href, label }: { href: string; label: string }) {
  const pathname = usePathname() ?? "";
  const active = href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      className={cn("nav-link", active ? "nav-link-active" : "text-muted-foreground hover:text-foreground")}
    >
      {label}
    </Link>
  );
}

function MainNav() {
  const { user } = useAuth();
  return (
    <nav className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1 gap-y-1">
      {user ? <NavLink href="/" label="Desk" /> : null}
      <NavLink href="/social" label="Social" />
      {user ? (
        <>
          <NavLink href="/tape" label="Tape" />
          <NavLink href="/perps" label="Perps" />
          <NavLink href="/rail" label="Rail" />
          <NavLink href="/futures" label="Futures" />
          <NavLink href="/radar" label="Radar" />
          <NavLink href="/expansion" label="Expansion" />
          <NavLink href="/chart" label="Chart" />
          <NavLink href="/request-ticker" label="Request" />
          <NavLink href="/favorites" label="Favorites" />
        </>
      ) : null}
      {user?.is_admin ? (
        <>
          <NavLink href="/admin/access" label="Access" />
          <NavLink href="/admin/api-access" label="API" />
          <NavLink href="/admin/wallets" label="Wallets" />
          <NavLink href="/admin/requests" label="Requests" />
        </>
      ) : null}
    </nav>
  );
}

function DesktopBar({
  title,
  trailing,
  subtitle,
}: {
  title: string;
  trailing?: ReactNode;
  subtitle?: ReactNode;
}) {
  return (
    <div className="hidden md:block">
      {/*
        Installed desktop PWAs (Windows/Edge “app”) often open ~800px wide.
        A single nowrap h-14 row clips Desk/Perps/Rail behind Sign in.
        Stack logo+auth, then wrap the tabs. Wide browsers still fit one row at xl.
      */}
      <div className="container mx-auto flex flex-col gap-2 px-4 py-2.5 xl:flex-row xl:items-center xl:gap-6">
        <div className="flex min-w-0 items-center justify-between gap-3 xl:contents">
          <div className="flex min-w-0 items-center gap-2.5">
            <SignalEngineLogo size="sm" />
            <p className="hidden truncate font-mono text-[11px] uppercase tracking-widest text-muted-foreground/70 lg:block">
              {title}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3 sm:gap-4">
            {trailing}
            {subtitle ? <div className="hidden max-w-[18rem] 2xl:block">{subtitle}</div> : null}
            <AuthNav />
          </div>
        </div>
        <MainNav />
      </div>
    </div>
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
      <header className="app-header sticky top-0 z-40 pt-[env(safe-area-inset-top)]">
        <div className="container mx-auto flex flex-col gap-2 px-3 py-3 sm:px-4 sm:py-3.5 md:hidden">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <SignalEngineLogo size="sm" />
              <p className="truncate font-mono text-[11px] uppercase tracking-widest text-muted-foreground/70">
                {title}
              </p>
            </div>
            <BuiltByNotes />
          </div>
          <MainNav />
          {(trailing || subtitle) ? (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              {trailing}
              {subtitle}
            </div>
          ) : null}
          <AuthNav />
        </div>
        <DesktopBar title={title} trailing={trailing} subtitle={subtitle} />
      </header>
    );
  }

  return (
    <header className="app-header border-b border-white/[0.05] pt-[env(safe-area-inset-top)] md:sticky md:top-0 md:z-40">
      <div className="container mx-auto flex flex-col gap-3 px-3 py-4 sm:px-4 sm:py-7 md:hidden">
        <div className="min-w-0 overflow-visible">
          <SignalEngineLogo size="lg" href={false} />
          <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 pl-[2.625rem]">
            <p className="text-sm font-light tracking-wide text-muted-foreground/75">
              {title}
            </p>
            <BuiltByNotes />
          </div>
        </div>
        <div className="flex min-w-0 flex-col items-start gap-2">
          <MainNav />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {trailing}
            {subtitle ? <div className="opacity-80">{subtitle}</div> : null}
            <AuthNav />
          </div>
        </div>
      </div>
      <DesktopBar title={title} trailing={trailing} subtitle={subtitle} />
    </header>
  );
}
