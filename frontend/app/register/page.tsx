"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";

export default function RegisterPage() {
  const router = useRouter();
  const { register, user, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email.trim(), username.trim(), password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto max-w-md px-4 py-16">
        <p className="label-caps">Account</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Create account</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Join discussions on tracked assets. Username is shown on posts.
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
              className="mt-2 w-full border border-white/[0.1] bg-transparent px-3 py-2 text-sm outline-none focus:border-white/[0.22]"
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
              className="mt-2 w-full border border-white/[0.1] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.22]"
            />
          </label>
          <label className="block">
            <span className="label-caps">Password</span>
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-2 w-full border border-white/[0.1] bg-transparent px-3 py-2 text-sm outline-none focus:border-white/[0.22]"
            />
            <span className="mt-1 block font-mono text-[10px] text-muted-foreground">
              At least 8 characters
            </span>
          </label>
          {error ? <p className="text-sm text-bearish">{error}</p> : null}
          <button
            type="submit"
            disabled={submitting}
            className="w-full border border-white/[0.12] px-3 py-2.5 font-mono text-xs uppercase tracking-wide transition-colors hover:bg-white/[0.06] disabled:opacity-50"
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
      </div>
    </main>
  );
}
