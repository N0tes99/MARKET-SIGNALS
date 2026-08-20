"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { LoginEnginePreview } from "@/components/login-engine-preview";
import { PasswordInput } from "@/components/password-input";
import { SiteHeader } from "@/components/site-header";

export default function RegisterPage() {
  const router = useRouter();
  const { register, user, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [checkEmail, setCheckEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user?.email_verified) {
      router.replace("/");
    }
  }, [loading, user, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setSubmitting(true);
    try {
      const created = await register(email.trim(), username.trim(), password);
      if (created.email_verified) {
        router.push("/");
      } else {
        setCheckEmail(created.email);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto px-4 py-12 md:py-16">
        <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-14 xl:grid-cols-[minmax(0,24rem)_minmax(0,28rem)] xl:justify-center">
          <div>
            <p className="label-caps">Account</p>
            <h1 className="mt-2 font-brand text-3xl font-medium tracking-tight">Create account</h1>

            {checkEmail ? (
              <div className="surface mt-8 space-y-4 p-5">
                <div>
                  <p className="text-sm text-foreground">Check your email</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    We sent a confirmation link to{" "}
                    <span className="text-foreground">{checkEmail}</span>. Open it to
                    activate your account.
                  </p>
                </div>
                <div className="border-t border-white/[0.06] pt-4">
                  <p className="label-caps text-muted-foreground/60">What happens next</p>
                  <ol className="mt-3 list-decimal space-y-2 pl-4 text-sm text-muted-foreground">
                    <li>Confirm your email, then sign in.</li>
                    <li>Wait on the waitlist until an admin grants access.</li>
                    <li>
                      When first allowed, add your personal setup key to an authenticator
                      app (Google Authenticator, Authy, etc.) and keep it there — you&apos;ll
                      need that app ongoing.
                    </li>
                    <li>
                      Unlock with the 6-digit code from the app whenever your session
                      resets (about every 12 hours).
                    </li>
                  </ol>
                </div>
                <Link
                  href="/login"
                  className="inline-block font-mono text-xs uppercase tracking-wide text-foreground underline-offset-4 hover:underline"
                >
                  Back to sign in
                </Link>
              </div>
            ) : (
              <>
                <p className="mt-2 text-sm text-muted-foreground">
                  Invite-only dashboard. We&apos;ll email a confirmation link, then
                  you wait for an admin grant and set up your personal authenticator.
                </p>

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
                  <label className="block">
                    <span className="label-caps">Username</span>
                    <input
                      type="text"
                      required
                      minLength={3}
                      maxLength={32}
                      pattern="[A-Za-z0-9_]+"
                      autoComplete="username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="glass-field mt-2 font-mono"
                    />
                  </label>
                  <label className="block">
                    <span className="label-caps">Password</span>
                    <PasswordInput
                      required
                      minLength={8}
                      autoComplete="new-password"
                      value={password}
                      onChange={setPassword}
                    />
                    <span className="mt-1 block font-mono text-[10px] text-muted-foreground">
                      At least 8 characters
                    </span>
                  </label>
                  <label className="block">
                    <span className="label-caps">Confirm password</span>
                    <PasswordInput
                      required
                      minLength={8}
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={setConfirmPassword}
                    />
                  </label>
                  {error ? <p className="text-sm text-bearish">{error}</p> : null}
                  <button
                    type="submit"
                    disabled={submitting}
                    className="btn-glass w-full"
                  >
                    {submitting ? "Creating…" : "Create account"}
                  </button>
                </form>

                <p className="mt-6 text-sm text-muted-foreground">
                  Already have an account?{" "}
                  <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
                    Sign in
                  </Link>
                </p>
              </>
            )}
          </div>

          <aside className="lg:sticky lg:top-8">
            <LoginEnginePreview />
          </aside>
        </div>
      </div>
    </main>
  );
}
