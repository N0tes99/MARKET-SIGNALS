"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";

function VerifyEmailInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { verifyEmail, resendVerificationEmail, user } = useAuth();
  const [status, setStatus] = useState<"idle" | "working" | "ok" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [resendNote, setResendNote] = useState<string | null>(null);

  useEffect(() => {
    const token = params?.get("token") ?? null;
    if (!token) {
      setStatus("error");
      setMessage("Missing verification token.");
      return;
    }
    let cancelled = false;
    setStatus("working");
    void (async () => {
      try {
        await verifyEmail(token);
        if (!cancelled) {
          setStatus("ok");
          setMessage("Email confirmed. You can post and favorite assets now.");
          setTimeout(() => router.replace("/social"), 1200);
        }
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setMessage(err instanceof Error ? err.message : "Verification failed");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params, verifyEmail, router]);

  async function onResend() {
    setResendNote(null);
    try {
      await resendVerificationEmail(user?.email);
      setResendNote("If an unverified account exists, we sent another email.");
    } catch (err) {
      setResendNote(err instanceof Error ? err.message : "Could not resend");
    }
  }

  return (
    <div className="surface mt-8 space-y-3 p-5">
      <p className="text-sm text-foreground">
        {status === "working" ? "Confirming your email…" : null}
        {status === "ok" ? message : null}
        {status === "error" ? message : null}
        {status === "idle" ? "Preparing…" : null}
      </p>
      {status === "error" ? (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => void onResend()}
            className="border border-white/[0.12] px-3 py-2 font-mono text-xs uppercase tracking-wide hover:bg-white/[0.06]"
          >
            Resend email
          </button>
          {resendNote ? (
            <p className="text-xs text-muted-foreground">{resendNote}</p>
          ) : null}
        </div>
      ) : null}
      <Link
        href="/login"
        className="inline-block font-mono text-xs uppercase tracking-wide text-muted-foreground underline-offset-4 hover:underline"
      >
        Sign in
      </Link>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto max-w-md px-4 py-16">
        <p className="label-caps">Account</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Verify email</h1>
        <Suspense fallback={<p className="mt-8 text-sm text-muted-foreground">Loading…</p>}>
          <VerifyEmailInner />
        </Suspense>
      </div>
    </main>
  );
}
