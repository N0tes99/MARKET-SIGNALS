"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { forgotPassword } from "@/services/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await forgotPassword(email.trim());
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send reset email");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto max-w-md px-4 py-16">
        <p className="label-caps">Account</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Forgot password</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Enter your email and we&apos;ll send a reset link if an account exists.
        </p>

        {done ? (
          <div className="surface mt-8 space-y-3 p-5">
            <p className="text-sm text-foreground">
              If an account exists for that address, we sent a password reset email.
              Check your inbox and spam folder.
            </p>
            <Link
              href="/login"
              className="inline-block font-mono text-xs uppercase tracking-wide text-muted-foreground underline-offset-4 hover:underline"
            >
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="surface mt-8 space-y-4 p-5">
            <label className="block">
              <span className="label-caps">Email</span>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="glass-field mt-2"
              />
            </label>
            {error ? <p className="text-sm text-bearish">{error}</p> : null}
            <button
              type="submit"
              disabled={submitting}
              className="btn-glass w-full"
            >
              {submitting ? "Sending…" : "Send reset link"}
            </button>
          </form>
        )}

        {!done ? (
          <p className="mt-6 text-sm text-muted-foreground">
            <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
              Back to sign in
            </Link>
          </p>
        ) : null}
      </div>
    </main>
  );
}
