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
