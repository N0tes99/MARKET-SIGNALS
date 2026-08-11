"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { PasswordInput } from "@/components/password-input";
import { SiteHeader } from "@/components/site-header";
import { resetPassword } from "@/services/api";

function ResetPasswordInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const token = params?.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("Missing reset token. Open the link from your email.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await resetPassword(token, password);
      await refresh();
      router.replace("/unlock");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset password");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="surface mt-8 space-y-3 p-5">
        <p className="text-sm text-bearish">Missing reset token. Open the link from your email.</p>
        <Link
          href="/forgot-password"
          className="inline-block font-mono text-xs uppercase tracking-wide text-muted-foreground underline-offset-4 hover:underline"
        >
          Request a new link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="surface mt-8 space-y-4 p-5">
      <label className="block">
        <span className="label-caps">New password</span>
        <PasswordInput
          required
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
        />
      </label>
      <label className="block">
        <span className="label-caps">Confirm password</span>
        <PasswordInput
          required
          autoComplete="new-password"
          value={confirm}
          onChange={setConfirm}
        />
      </label>
      {error ? <p className="text-sm text-bearish">{error}</p> : null}
      <button
        type="submit"
        disabled={submitting}
        className="w-full border border-white/[0.12] px-3 py-2.5 font-mono text-xs uppercase tracking-wide transition-colors hover:bg-white/[0.06] disabled:opacity-50"
      >
        {submitting ? "Saving…" : "Set new password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto max-w-md px-4 py-16">
        <p className="label-caps">Account</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Reset password</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Choose a new password for your Signal Engine account.
        </p>
        <Suspense fallback={<p className="mt-8 text-sm text-muted-foreground">Loading…</p>}>
          <ResetPasswordInner />
        </Suspense>
        <p className="mt-6 text-sm text-muted-foreground">
          <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
