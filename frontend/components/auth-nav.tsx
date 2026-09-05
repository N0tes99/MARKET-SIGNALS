"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth-provider";

export function AuthNav() {
  const { user, loading, logout, resendVerificationEmail } = useAuth();

  if (loading) {
    return (
      <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground/60">
        …
      </span>
    );
  }

  if (!user) {
    return (
      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <Link
          href="/login"
          className="nav-link text-muted-foreground hover:text-foreground"
        >
          Sign in
        </Link>
        <Link
          href="/register"
          className="btn-glass whitespace-nowrap px-2.5 py-1.5 sm:px-3"
        >
          Create account
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-3 md:flex-nowrap">
      {!user.email_verified ? (
        <button
          type="button"
          onClick={() => void resendVerificationEmail()}
          className="font-mono text-[11px] uppercase tracking-widest text-amber-200/80 transition-colors hover:text-foreground"
          title="Resend confirmation email"
        >
          Verify email
        </button>
      ) : null}
      <Link
        href={`/u/${encodeURIComponent(user.username)}`}
        className="font-mono text-[11px] tracking-wide text-foreground/90 underline-offset-4 hover:underline"
      >
        {user.username}
      </Link>
      <Link
        href="/settings/password"
        className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
      >
        Password
      </Link>
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
