/** Session-scoped last-known payloads so the dashboard paints before the API. */

export function readSessionSnapshot<T>(key: string): T | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return undefined;
    return JSON.parse(raw) as T;
  } catch {
    return undefined;
  }
}

export function writeSessionSnapshot(key: string, value: unknown): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* quota / private mode */
  }
}

export const ASSETS_SNAPSHOT_KEY = "se.assets.v1";
export const PAPER_SNAPSHOT_KEY = "se.paper.v1";
