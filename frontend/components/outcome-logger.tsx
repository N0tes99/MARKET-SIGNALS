"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import {
  fetchOutcomeStats,
  fetchSignals,
  logCurrentSignal,
  recordSignalOutcome,
  type SignalOutcome,
} from "@/services/api";
import { cn } from "@/lib/utils";

interface OutcomeLoggerProps {
  symbol: string;
}

function outcomeColor(outcome: string | null | undefined): string {
  switch (outcome) {
    case "win":
      return "text-bullish";
    case "loss":
      return "text-bearish";
    case "breakeven":
      return "text-neutral";
    default:
      return "text-muted-foreground";
  }
}

export function OutcomeLogger({ symbol }: OutcomeLoggerProps) {
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  const signalsQuery = useQuery({
    queryKey: ["signals", symbol],
    queryFn: () => fetchSignals(symbol, 12),
    enabled: Boolean(user?.is_admin),
  });

  const statsQuery = useQuery({
    queryKey: ["outcome-stats", symbol],
    queryFn: () => fetchOutcomeStats(symbol),
    enabled: Boolean(user?.is_admin),
  });

  const logMutation = useMutation({
    mutationFn: () => logCurrentSignal(symbol),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["signals", symbol] });
      void queryClient.invalidateQueries({ queryKey: ["outcome-stats", symbol] });
      void queryClient.invalidateQueries({ queryKey: ["similarity", symbol] });
    },
  });

  const outcomeMutation = useMutation({
    mutationFn: ({
      id,
      outcome,
      realizedReturnPct,
    }: {
      id: string;
      outcome: SignalOutcome;
      realizedReturnPct?: number;
    }) => recordSignalOutcome(symbol, id, outcome, realizedReturnPct),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["signals", symbol] });
      void queryClient.invalidateQueries({ queryKey: ["outcome-stats", symbol] });
      void queryClient.invalidateQueries({ queryKey: ["similarity", symbol] });
    },
  });

  // Admin-only coaching log (entry / TP / Hit / Miss).
  if (authLoading || !user?.is_admin) {
    return null;
  }

  const signals = signalsQuery.data ?? [];
  const stats = statsQuery.data;
  const openSignals = signals.filter((s) => !s.outcome);

  return (
    <div className="surface mt-3 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="label-caps">Outcome log</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Admin only — log the thesis (entry / TP), then mark Hit / Miss with realized return.
          </p>
        </div>
        <button
          type="button"
          onClick={() => logMutation.mutate()}
          disabled={logMutation.isPending}
          className="border border-white/[0.1] px-3 py-2 font-mono text-xs uppercase tracking-wide text-foreground transition-colors hover:bg-white/[0.06] disabled:opacity-50"
        >
          {logMutation.isPending ? "Logging…" : "Log current signal"}
        </button>
      </div>

      {stats && (
        <div className="mt-4 flex flex-wrap gap-x-8 gap-y-2 border-t border-white/[0.06] pt-4 font-mono text-xs text-muted-foreground">
          <span>
            resolved {stats.resolved}/{stats.total_logged}
          </span>
          <span className="text-bullish">wins {stats.wins}</span>
          <span className="text-bearish">losses {stats.losses}</span>
          <span>win rate {stats.win_rate.toFixed(0)}%</span>
          <span>avg ret {stats.avg_return_pct.toFixed(2)}%</span>
        </div>
      )}

      {signalsQuery.isLoading ? (
        <div className="mt-4 h-20 animate-pulse bg-muted/30" />
      ) : signals.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">
          No signals logged yet. Click &ldquo;Log current signal&rdquo; when you see a setup worth
          tracking.
        </p>
      ) : (
        <ul className="mt-4 space-y-4 border-t border-white/[0.06] pt-4">
          {signals.map((signal) => (
            <li key={signal.id} className="space-y-2">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <div>
                  <p className="font-mono text-sm text-foreground/90">
                    {signal.confidence.toFixed(0)}% · grade {signal.trade_grade} ·{" "}
                    {signal.trade_state.toLowerCase()}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                    {new Date(signal.timestamp).toLocaleString()}
                    {signal.entry_price != null && ` · entry ${signal.entry_price.toFixed(2)}`}
                    {signal.take_profit != null && ` · tp ${signal.take_profit.toFixed(2)}`}
                  </p>
                </div>
                <p className={cn("font-mono text-xs uppercase", outcomeColor(signal.outcome))}>
                  {signal.outcome
                    ? `${signal.outcome}${
                        signal.realized_return_pct != null
                          ? ` ${signal.realized_return_pct > 0 ? "+" : ""}${signal.realized_return_pct.toFixed(2)}%`
                          : ""
                      }`
                    : "open"}
                </p>
              </div>

              {!signal.outcome && (
                <div className="flex flex-wrap gap-2">
                  {(
                    [
                      ["win", "Hit"],
                      ["loss", "Miss"],
                      ["breakeven", "Flat"],
                      ["no_trade", "Skip"],
                    ] as const
                  ).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      disabled={outcomeMutation.isPending}
                      onClick={() => {
                        const raw =
                          value === "win" || value === "loss"
                            ? window.prompt(
                                value === "win"
                                  ? "Realized return % (e.g. 0.4 for +0.4%)"
                                  : "Realized return % (negative for loss, e.g. -0.3)",
                                value === "win" ? "0.4" : "-0.3",
                              )
                            : null;
                        const parsed =
                          raw == null || raw.trim() === "" ? undefined : Number.parseFloat(raw);
                        outcomeMutation.mutate({
                          id: signal.id,
                          outcome: value,
                          realizedReturnPct: Number.isFinite(parsed) ? parsed : undefined,
                        });
                      }}
                      className="border border-white/[0.1] px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {openSignals.length > 0 && (
        <p className="mt-4 font-mono text-[10px] text-muted-foreground">
          {openSignals.length} open — resolve when you know the result
        </p>
      )}
    </div>
  );
}
