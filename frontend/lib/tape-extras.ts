import { CRYPTO_SYMBOLS } from "@/config/assets";

const STORAGE_KEY = "se_tape_extras";
const CRYPTO = new Set<string>(CRYPTO_SYMBOLS);
const TICKER = /^[A-Z]{1,5}$/;

export function normalizeTapeTicker(raw: string): string | null {
  const symbol = raw.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 5);
  if (!TICKER.test(symbol) || CRYPTO.has(symbol)) return null;
  return symbol;
}

export function readTapeExtras(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as unknown;
    if (!Array.isArray(parsed)) return [];
    return [
      ...new Set(
        parsed
          .filter((item): item is string => typeof item === "string")
          .map(normalizeTapeTicker)
          .filter((item): item is string => Boolean(item)),
      ),
    ].slice(0, 24);
  } catch {
    return [];
  }
}

export function writeTapeExtras(symbols: string[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(symbols.slice(0, 24)));
}
