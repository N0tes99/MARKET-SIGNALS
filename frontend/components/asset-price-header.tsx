"use client";

import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import { fetchQuote } from "@/services/api";

function formatPrice(price: number): string {
  if (price >= 1000) {
    return price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  if (price >= 1) {
    return price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    });
  }
  return price.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 8,
  });
}

export function AssetPriceHeader({ symbol }: { symbol: string }) {
  const { data } = useQuery({
    queryKey: ["quote", symbol],
    queryFn: () => fetchQuote(symbol),
    staleTime: 45_000,
    refetchInterval: 120_000,
    refetchOnWindowFocus: false,
  });

  if (!data?.available || data.price == null) {
    return null;
  }

  const change = data.change_pct;
  const changeClass =
    change == null
      ? "text-muted-foreground"
      : change > 0
        ? "text-bullish"
        : change < 0
          ? "text-bearish"
          : "text-neutral";

  return (
    <p className="flex items-baseline gap-3 font-mono">
      <span className="text-xl text-foreground/90">${formatPrice(data.price)}</span>
      {change != null ? (
        <span className={cn("text-sm", changeClass)}>
          {change > 0 ? "+" : ""}
          {change.toFixed(2)}%
        </span>
      ) : null}
    </p>
  );
}
