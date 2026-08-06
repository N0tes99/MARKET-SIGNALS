"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";
import { TRACKED_SYMBOLS } from "@/config/assets";
import { addFavorite, fetchFavorites, removeFavorite } from "@/services/api";

export default function FavoritesPage() {
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = useState<string>(TRACKED_SYMBOLS[0] ?? "BTC");
  const [error, setError] = useState<string | null>(null);
  const canWrite = Boolean(user?.email_verified);

  const favoritesQuery = useQuery({
    queryKey: ["favorites"],
    queryFn: fetchFavorites,
    enabled: Boolean(user),
  });

  const addMutation = useMutation({
    mutationFn: (sym: string) => addFavorite(sym),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (sym: string) => removeFavorite(sym),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  const favorited = useMemo(
    () => new Set((favoritesQuery.data ?? []).map((f) => f.symbol)),
    [favoritesQuery.data],
  );

  async function onAdd(event: FormEvent) {
    event.preventDefault();
    if (!canWrite) return;
    setError(null);
    try {
      await addMutation.mutateAsync(symbol);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add favorite");
    }
  }

  if (!authLoading && !user) {
    return (
      <main className="min-h-screen">
        <SiteHeader compact />
        <div className="container mx-auto max-w-lg px-4 py-16">
          <p className="label-caps">Watchlist</p>
          <h1 className="mt-2 text-2xl font-light tracking-tight">Favorites</h1>
          <p className="mt-4 text-sm text-muted-foreground">
            <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
              Sign in
            </Link>{" "}
            to save tickers from the site list.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <SiteHeader compact />
      <div className="container mx-auto max-w-lg px-4 py-10">
        <p className="label-caps">Watchlist</p>
        <h1 className="mt-2 text-2xl font-light tracking-tight">Favorites</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Pick symbols from the tracked universe. Opens the same asset pages as the dashboard.
        </p>

        {user && !user.email_verified ? (
          <p className="surface mt-6 p-4 text-sm text-muted-foreground">
            Verify your email to manage favorites.{" "}
            <Link href="/verify-email" className="text-foreground underline-offset-4 hover:underline">
              Verify email
            </Link>
          </p>
        ) : null}

        {canWrite ? (
          <form onSubmit={onAdd} className="surface mt-6 flex flex-wrap items-end gap-3 p-5">
            <label className="min-w-[10rem] flex-1">
              <span className="label-caps">Add ticker</span>
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="mt-2 w-full border border-white/[0.1] bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-white/[0.22]"
              >
                {TRACKED_SYMBOLS.map((sym) => (
                  <option key={sym} value={sym} className="bg-background text-foreground">
                    {sym}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              disabled={addMutation.isPending || favorited.has(symbol)}
              className="border border-white/[0.12] px-3 py-2 font-mono text-xs uppercase tracking-wide hover:bg-white/[0.06] disabled:opacity-50"
            >
              {favorited.has(symbol) ? "Added" : "Add"}
            </button>
            {error ? <p className="basis-full text-sm text-bearish">{error}</p> : null}
          </form>
        ) : null}

        <div className="surface mt-6 p-5">
          <h2 className="label-caps">Your list</h2>
          {favoritesQuery.isLoading ? (
            <p className="mt-4 font-mono text-xs text-muted-foreground">Loading…</p>
          ) : null}
          {favoritesQuery.isError ? (
            <p className="mt-4 text-sm text-bearish">Could not load favorites.</p>
          ) : null}
          {!favoritesQuery.isLoading && (favoritesQuery.data?.length ?? 0) === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">No favorites yet.</p>
          ) : null}
          <ul className="mt-4 divide-y divide-white/[0.06]">
            {(favoritesQuery.data ?? []).map((fav) => (
              <li
                key={fav.symbol}
                className="flex items-center justify-between gap-3 py-3 first:pt-0"
              >
                <Link
                  href={`/assets/${fav.symbol}`}
                  className="font-mono text-sm text-foreground underline-offset-4 hover:underline"
                >
                  {fav.symbol}
                </Link>
                {canWrite ? (
                  <button
                    type="button"
                    disabled={removeMutation.isPending}
                    onClick={() => void removeMutation.mutateAsync(fav.symbol)}
                    className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground"
                  >
                    Remove
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  );
}
