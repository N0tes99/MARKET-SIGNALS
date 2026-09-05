"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { PasswordInput } from "@/components/password-input";
import { SiteHeader } from "@/components/site-header";
import { changePassword } from "@/services/api";

export default function ChangePasswordPage() {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login?next=/settings/password");
    }
  }, [loading, user, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (newPassword !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      await refresh();
      router.replace("/unlock?next=/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change password");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading || !user) {
    return (
      <main className="min-h-screen">
        <SiteHeader compact />
        <p className="p-8 font-mono text-[11px] text-muted-foreground/50">Loading…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact title="Password" />
      <div className="container mx-auto max-w-md px-4 py-10">
        <p className="label-caps">Settings</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Change password</h1>
        <p className="mt-2 text-sm text-muted-foreground/75">
          {user.is_admin
            ? "Admin accounts cannot reset by email. Use this page while unlocked. A password change signs out other devices and requires a fresh authenticator code."
            : "Changing your password signs out other devices."}
        </p>

        <form onSubmit={onSubmit} className="surface mt-8 space-y-4 p-5">
          <label className="block">
            <span className="label-caps">Current password</span>
            <PasswordInput
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={setCurrentPassword}
            />
          </label>
          <label className="block">
            <span className="label-caps">New password</span>
            <PasswordInput
              required
              minLength={8}
              autoComplete="new-password"
              value={newPassword}
              onChange={setNewPassword}
            />
          </label>
          <label className="block">
            <span className="label-caps">Confirm new password</span>
            <PasswordInput
              required
              minLength={8}
              autoComplete="new-password"
              value={confirm}
              onChange={setConfirm}
            />
          </label>
          {error ? <p className="font-mono text-[11px] text-bearish/80">{error}</p> : null}
          <button
            type="submit"
            disabled={submitting}
            className="w-full border border-white/[0.1] bg-foreground/90 py-2.5 font-mono text-[11px] uppercase tracking-widest text-background disabled:opacity-40"
          >
            {submitting ? "Saving…" : "Save password"}
          </button>
        </form>

        <p className="mt-6 font-mono text-[10px] text-muted-foreground/45">
          <Link href="/settings/api-keys" className="underline-offset-2 hover:underline">
            API keys
          </Link>
        </p>
      </div>
    </main>
  );
}
