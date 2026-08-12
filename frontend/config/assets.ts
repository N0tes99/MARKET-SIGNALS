/** Dashboard watchlist — keep in sync with backend/app/market_data/symbols.py */

export type AssetClass = "crypto" | "stock" | "etf";

export const CRYPTO_SYMBOLS = [
  "BTC",
  "ETH",
  "SOL",
  "SUI",
  "XRP",
  "ADA",
  "AVAX",
  "LINK",
  "DOGE",
  "DOT",
  "LTC",
  "ATOM",
  "NEAR",
  "ARB",
  "APT",
  "INJ",
  "TAO",
  "WIF",
  "PEPE",
  "RENDER",
  "FET",
  "TIA",
  "SEI",
  "JUP",
  "OP",
] as const;

export const ETF_SYMBOLS = [
  "SPY",
  "QQQ",
  "IWM",
  "VOO",
  "DIA",
  "ARKK",
  "SOXL",
  "SMH",
  "IBIT",
  "XLE",
  "XBI",
  "TQQQ",
] as const;

export const STOCK_SYMBOLS = [
  "AAPL",
  "MSFT",
  "NVDA",
  "GOOGL",
  "META",
  "AMZN",
  "TSLA",
  "AMD",
  "NFLX",
  "NOW",
  "CRM",
  "PLTR",
  "COIN",
  "SMCI",
  "MSTR",
  "HOOD",
  "RKLB",
  "IONQ",
  "ARM",
  "SHOP",
  "SNOW",
  "UBER",
  "RBLX",
] as const;

export const TRACKED_SYMBOLS = [
  ...CRYPTO_SYMBOLS,
  ...ETF_SYMBOLS,
  ...STOCK_SYMBOLS,
] as const;

export type TrackedSymbol = (typeof TRACKED_SYMBOLS)[number];

/** Relative watchlist size (approx market cap / AUM). Used by the heat map. */
export const HEATMAP_WEIGHT: Record<string, number> = {
  BTC: 100,
  ETH: 28,
  XRP: 10,
  SOL: 8,
  DOGE: 3.2,
  ADA: 2.2,
  AVAX: 1.4,
  LINK: 1.2,
  SUI: 1.1,
  DOT: 0.8,
  LTC: 0.6,
  NEAR: 0.5,
  PEPE: 0.4,
  APT: 0.4,
  TAO: 0.35,
  ARB: 0.3,
  ATOM: 0.3,
  RENDER: 0.25,
  OP: 0.22,
  INJ: 0.2,
  FET: 0.2,
  WIF: 0.16,
  TIA: 0.15,
  SEI: 0.15,
  JUP: 0.15,
  SPY: 60,
  VOO: 50,
  QQQ: 30,
  IBIT: 8,
  IWM: 7,
  DIA: 4,
  XLE: 3.8,
  SMH: 2.6,
  TQQQ: 2.4,
  SOXL: 1.1,
  ARKK: 0.8,
  XBI: 0.7,
  NVDA: 40,
  MSFT: 38,
  AAPL: 35,
  AMZN: 24,
  GOOGL: 22,
  META: 16,
  TSLA: 12,
  NFLX: 4.2,
  AMD: 3.2,
  PLTR: 3,
  CRM: 2.5,
  NOW: 2.1,
  UBER: 1.8,
  ARM: 1.5,
  SHOP: 1.5,
  COIN: 0.85,
  MSTR: 0.8,
  HOOD: 0.7,
  SNOW: 0.7,
  RBLX: 0.55,
  SMCI: 0.4,
  RKLB: 0.25,
  IONQ: 0.16,
};

export function heatmapWeight(symbol: string): number {
  return HEATMAP_WEIGHT[symbol.toUpperCase()] ?? 1;
}

export const ASSET_SECTIONS: { label: string; class: AssetClass; symbols: readonly string[] }[] = [
  { label: "Crypto", class: "crypto", symbols: CRYPTO_SYMBOLS },
  { label: "ETFs", class: "etf", symbols: ETF_SYMBOLS },
  { label: "Stocks", class: "stock", symbols: STOCK_SYMBOLS },
];

export function assetClassLabel(assetClass: AssetClass): string {
  switch (assetClass) {
    case "crypto":
      return "crypto";
    case "etf":
      return "etf";
    default:
      return "stock";
  }
}

/** Strip pair suffixes (BTCUSDT, BTC-USD) so CoinGlass gets a base ticker. */
export function toCoinglassSymbol(symbol: string): string {
  const upper = symbol.trim().toUpperCase();
  return upper
    .replace(/[-_/]/g, "")
    .replace(/(USDT|USDC|USD|BUSD|PERP)$/i, "");
}

export function isCryptoSymbol(symbol: string): boolean {
  const base = toCoinglassSymbol(symbol);
  return (CRYPTO_SYMBOLS as readonly string[]).includes(base);
}

/** Public CoinGlass liquidations page for a coin, e.g. /liquidations/BTC */
export function coinglassLiquidationsUrl(symbol: string): string | null {
  if (!isCryptoSymbol(symbol)) return null;
  const coin = toCoinglassSymbol(symbol);
  if (!coin) return null;
  return `https://www.coinglass.com/liquidations/${encodeURIComponent(coin)}`;
}
