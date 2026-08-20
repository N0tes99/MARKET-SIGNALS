"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";
import {
  analyzeChartScreenshot,
  fetchChartAnalysisStatus,
  type ChartAnalysis,
  type ChartAnalysisStatus,
  type ChartBias,
  type ChartExecutionHint,
  type ChartPositionIdea,
} from "@/services/api";

const ACCEPT = "image/png,image/jpeg,image/webp,image/gif";

function biasColor(bias: ChartBias): string {
  if (bias === "long") return "text-bullish";
  if (bias === "short") return "text-bearish";
  return "text-muted-foreground";
}

function hintColor(hint: ChartExecutionHint): string {
  if (hint === "EXECUTE") return "text-bullish";
  if (hint === "WATCH") return "text-neutral";
  return "text-muted-foreground";
}

function trendColor(trend: string): string {
  if (trend === "bullish") return "text-bullish";
  if (trend === "bearish") return "text-bearish";
  return "text-neutral";
}

function sourceLabel(source: string): string {
  if (source === "openai") return "gpt-4o-mini vision";
  if (source === "groq") return "groq vision";
  if (source === "gemini") return "gemini-2.0-flash vision";
  if (source === "local_llm") return "LM Studio / local node";
  if (source === "local") return "desk engines (no vision)";
  return source;
}

export function ChartAnalyzerPanel() {
  const { user } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [symbolHint, setSymbolHint] = useState("");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChartAnalysis | null>(null);
  const [status, setStatus] = useState<ChartAnalysisStatus | null>(null);

  const assignFile = useCallback((next: File | null) => {
    setFile(next);
    setResult(null);
    setError(null);
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return next ? URL.createObjectURL(next) : null;
    });
  }, []);

  useEffect(() => {
    if (!user) return;
    void fetchChartAnalysisStatus()
      .then(setStatus)
      .catch(() => undefined);
  }, [user]);

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    assignFile(event.target.files?.[0] ?? null);
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) assignFile(dropped);
  }

  async function onAnalyze() {
    if (!file && !symbolHint.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const analysis = await analyzeChartScreenshot(file, {
        note,
        symbolHint,
      });
      setResult(analysis);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="surface p-5 sm:p-6">
        <p className="label-caps">Upload</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Screenshot of a chart, tape, options chain, or ticket. With LM Studio
          running, the local Qwen vision model reads the image. Without it, type
          a tracked ticker and desk engines still map locations. Engines decide —
          this does not place orders.
        </p>
        {status ? (
          <p className="mt-3 font-mono text-[10px] leading-relaxed text-muted-foreground/70">
            Backend · {sourceLabel(status.source)}. {status.hint}
          </p>
        ) : null}

        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "mt-5 flex min-h-40 w-full flex-col items-center justify-center border border-dashed px-4 py-8 text-center transition-colors",
            dragging
              ? "border-white/30 bg-white/[0.04]"
              : "border-white/[0.12] hover:border-white/20 hover:bg-white/[0.02]",
          )}
        >
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={preview}
              alt="Chart screenshot preview"
              className="max-h-64 w-auto object-contain"
            />
          ) : (
            <>
              <span className="font-mono text-[11px] uppercase tracking-widest text-foreground/80">
                Drop a screenshot
              </span>
              <span className="mt-2 font-mono text-[10px] text-muted-foreground/60">
                PNG, JPEG, WebP · max 8MB
              </span>
            </>
          )}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={onPick}
        />

        {file ? (
          <p className="mt-3 font-mono text-[10px] text-muted-foreground/70">
            {file.name} · {(file.size / 1024).toFixed(0)} KB
          </p>
        ) : null}

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label-caps">Symbol hint</span>
            <input
              value={symbolHint}
              onChange={(event) => setSymbolHint(event.target.value.toUpperCase())}
              placeholder="BTC"
              maxLength={16}
              className="mt-2 w-full border border-white/[0.1] bg-transparent px-3 py-2 font-mono text-sm uppercase outline-none focus:border-white/[0.22]"
            />
          </label>
          <label className="block sm:col-span-2">
            <span className="label-caps">Your note</span>
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              maxLength={500}
              placeholder="I was thinking a long if this high holds…"
              className="mt-2 w-full resize-y border border-white/[0.1] bg-transparent px-3 py-2 text-sm outline-none focus:border-white/[0.22]"
            />
          </label>
        </div>

        {error ? <p className="mt-4 text-sm text-bearish">{error}</p> : null}

        <button
          type="button"
          disabled={(!file && !symbolHint.trim()) || busy || !user}
          onClick={() => void onAnalyze()}
          className="mt-5 w-full border border-white/[0.12] px-3 py-2.5 font-mono text-xs uppercase tracking-wide transition-colors hover:bg-white/[0.06] disabled:opacity-50"
        >
          {busy ? "Reading…" : "Analyze"}
        </button>
      </section>

      {result ? <AnalysisResult data={result} /> : null}
    </div>
  );
}

function AnalysisResult({ data }: { data: ChartAnalysis }) {
  const { reading, engine_grounding: grounding } = data;
  return (
    <div className="space-y-6">
      <section className="surface p-5 sm:p-6">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="label-caps">Reading</h2>
          <span className="font-mono text-[10px] text-muted-foreground">
            {sourceLabel(data.source)}
          </span>
        </div>
        <div className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
          <Meta label="Symbol" value={reading.symbol ?? "—"} />
          <Meta
            label="Trend"
            value={reading.trend}
            className={trendColor(reading.trend)}
          />
          <Meta label="Timeframe" value={reading.timeframe ?? "—"} />
          <Meta label="Quality" value={reading.image_quality} />
          {reading.last_price != null ? (
            <Meta label="Last" value={String(reading.last_price)} />
          ) : null}
        </div>
        <p className="mt-4 text-sm leading-relaxed text-foreground/90">{data.thesis}</p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          {reading.structure}
        </p>
        {reading.key_levels.length > 0 ? (
          <ul className="mt-4 space-y-1.5 border-t border-white/[0.06] pt-4">
            {reading.key_levels.map((level) => (
              <li key={level} className="font-mono text-[11px] text-muted-foreground">
                {level}
              </li>
            ))}
          </ul>
        ) : null}
        {reading.observations.length > 0 ? (
          <ul className="mt-3 space-y-1.5">
            {reading.observations.map((item) => (
              <li key={item} className="font-mono text-[11px] leading-relaxed text-muted-foreground/80">
                {item}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section>
        <h2 className="label-caps">Possible positions</h2>
        <p className="mt-1 mb-4 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          Analysis, not an order
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          {data.positions.map((position) => (
            <PositionCard key={`${position.bias}-${position.setup_name}`} idea={position} />
          ))}
        </div>
      </section>

      {grounding ? (
        <section className="surface p-5 sm:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="label-caps">Desk evidence</h2>
            <span
              className={cn(
                "font-mono text-[10px] uppercase tracking-widest",
                grounding.alignment === "agrees"
                  ? "text-bullish"
                  : grounding.alignment === "conflicts"
                    ? "text-bearish"
                    : "text-neutral",
              )}
            >
              {grounding.alignment}
            </span>
          </div>
          <div className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
            <Meta label="State" value={grounding.trade_state.toLowerCase()} />
            <Meta label="Grade" value={grounding.trade_grade} />
            <Meta label="Signal" value={grounding.execution_signal.toLowerCase()} />
            <Meta label="Score" value={grounding.opportunity_score.toFixed(0)} />
          </div>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            {grounding.summary}
          </p>
          {grounding.alignment_notes.map((item) => (
            <p key={item} className="mt-2 text-xs text-neutral">
              {item}
            </p>
          ))}
          {grounding.asset_path ? (
            <Link
              href={grounding.asset_path}
              className="mt-4 inline-block font-mono text-[11px] uppercase tracking-widest text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              Open {grounding.symbol} desk
            </Link>
          ) : null}
        </section>
      ) : null}

      {data.conflicts.length > 0 ? (
        <section className="surface p-5">
          <h2 className="label-caps">Conflicts</h2>
          <ul className="mt-3 space-y-1.5">
            {data.conflicts.map((conflict) => (
              <li key={conflict} className="text-xs text-neutral">
                {conflict}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <p className="font-mono text-[10px] leading-relaxed text-muted-foreground/50">
        {data.disclaimer}
      </p>
    </div>
  );
}

function PositionCard({ idea }: { idea: ChartPositionIdea }) {
  return (
    <article className="surface p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="label-caps">{idea.setup_name}</h3>
        <span className="shrink-0 font-mono text-sm">{idea.confidence.toFixed(0)}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
        <Meta label="Bias" value={idea.bias.replace("_", " ")} className={biasColor(idea.bias)} />
        <Meta
          label="Hint"
          value={idea.execution_hint.toLowerCase()}
          className={hintColor(idea.execution_hint)}
        />
      </div>
      <p className="mt-4 text-sm leading-relaxed text-foreground/85">{idea.thesis}</p>
      <div className="mt-4 space-y-2 border-t border-white/[0.06] pt-3">
        {idea.entry_zone ? <Meta label="Entry" value={idea.entry_zone} /> : null}
        {idea.invalidation ? <Meta label="Invalidation" value={idea.invalidation} /> : null}
        {idea.targets.length > 0 ? (
          <Meta label="Targets" value={idea.targets.join(" · ")} />
        ) : null}
        {idea.risk_notes ? (
          <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
            {idea.risk_notes}
          </p>
        ) : null}
      </div>
    </article>
  );
}

function Meta({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div>
      <p className="label-caps">{label}</p>
      <p className={cn("mt-1 font-mono text-sm", className ?? "text-foreground/90")}>{value}</p>
    </div>
  );
}
