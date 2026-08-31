/** Allow only same-origin relative paths (blocks //evil.com and javascript:). */
export function safeNextPath(raw: string | null | undefined, fallback = "/"): string {
  if (!raw) return fallback;
  const trimmed = raw.trim();
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) return fallback;
  if (trimmed.includes("\\") || /[\u0000-\u001F\u007F]/.test(trimmed)) return fallback;
  return trimmed;
}
