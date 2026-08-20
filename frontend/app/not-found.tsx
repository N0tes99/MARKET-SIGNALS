import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6">
      <p className="label-caps">404</p>
      <h1 className="text-xl font-light tracking-tight">Page not found</h1>
      <Link
        href="/"
        className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
      >
        Back to desk
      </Link>
    </main>
  );
}
