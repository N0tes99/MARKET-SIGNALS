"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  QUOTES_SNAPSHOT_KEY,
  readSessionSnapshot,
  writeSessionSnapshot,
} from "@/lib/session-snapshot";
import { fetchQuotes, type AssetQuote } from "@/services/api";

function isTabVisible(): boolean {
  if (typeof document === "undefined") return true;
  return document.visibilityState === "visible";
}

function quotesWarming(quotes: AssetQuote[] | undefined): boolean {
  if (!quotes?.length) return true;
  const ready = quotes.filter((quote) => quote.available).length;
  return ready < Math.ceil(quotes.length * 0.5);
}

export function useQuotes() {
  const query = useQuery({
    queryKey: ["quotes"],
    queryFn: fetchQuotes,
    staleTime: 60_000,
    gcTime: 15 * 60_000,
    refetchInterval: (q) => {
      if (!isTabVisible()) return false;
      if (quotesWarming(q.state.data as AssetQuote[] | undefined)) return 5_000;
      return 60_000;
    },
    refetchOnWindowFocus: true,
    placeholderData: (previous) =>
      previous ?? readSessionSnapshot<AssetQuote[]>(QUOTES_SNAPSHOT_KEY),
  });

  useEffect(() => {
    if (query.data?.some((quote) => quote.available)) {
      writeSessionSnapshot(QUOTES_SNAPSHOT_KEY, query.data);
    }
  }, [query.data]);

  return query;
}
