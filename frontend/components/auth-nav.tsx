"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth-provider";

export function AuthNav() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return (
      <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground/60">
        …
      </span>
    );
  }

  if (!user) {
    return (
      <div className="flex items-center gap-3">
        <Link
          href="/login"
          className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
        >
          Sign in
        </Link>
        <Link
          href="/register"
          className="border border-white/[0.12] px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-foreground transition-colors hover:bg-white/[0.06]"
        >
          Create account
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-[11px] tracking-wide text-foreground/90">
        {user.username}
      </span>
      <button
        type="button"
        onClick={() => void logout()}
        className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
      >
        Sign out
      </button>
    </div>
  );
}
