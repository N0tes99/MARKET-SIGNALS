"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6">
      <p className="label-caps">Error</p>
      <h1 className="text-xl font-light tracking-tight">Something went wrong</h1>
      <p className="max-w-md text-center text-sm text-muted-foreground">
        {error.message || "The page failed to render."}
      </p>
      <button
        type="button"
        onClick={() => reset()}
        className="font-mono text-[11px] uppercase tracking-widest text-foreground underline-offset-4 hover:underline"
      >
        Try again
      </button>
    </main>
  );
}
