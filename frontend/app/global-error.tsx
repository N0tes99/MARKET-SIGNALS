"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          background: "#06090c",
          color: "#e8e4d9",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 12,
          padding: 24,
        }}
      >
        <h1 style={{ fontSize: 20, fontWeight: 400, margin: 0 }}>Something went wrong</h1>
        <p style={{ color: "#8a867a", fontSize: 14, margin: 0, textAlign: "center", maxWidth: 420 }}>
          {error.message || "The app failed to start."}
        </p>
        <button
          type="button"
          onClick={() => reset()}
          style={{
            background: "transparent",
            color: "#e8e4d9",
            border: "1px solid #3a3832",
            borderRadius: 6,
            padding: "8px 14px",
            cursor: "pointer",
            fontFamily: "ui-monospace, monospace",
            fontSize: 12,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
