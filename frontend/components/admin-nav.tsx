"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const TABS = [
  { href: "/admin/access", label: "Grants" },
  { href: "/admin/api-access", label: "API keys" },
  { href: "/admin/wallets", label: "Wallets" },
  { href: "/admin/requests", label: "Requests" },
] as const;

export function AdminNav() {
  const pathname = usePathname() ?? "";
  return (
    <nav className="mt-6 flex flex-wrap gap-2 border-b border-white/[0.06] pb-3">
      {TABS.map((tab) => {
        const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "border px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors",
              active
                ? "border-foreground/25 bg-foreground/10 text-foreground"
                : "border-white/[0.08] text-muted-foreground/60 hover:text-foreground/80",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
