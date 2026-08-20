"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";

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
    void fetchChartAnalysisStatus()
      .then(setStatus)
      .catch(() => undefined);
  }, []);

  async function runScan(nextFile: File | null) {
    if (!nextFile && !symbolHint.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const analysis = await analyzeChartScreenshot(nextFile, {
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

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] ?? null;
    assignFile(next);
    if (next) void runScan(next);
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) {
      assignFile(dropped);
      void runScan(dropped);
    }
  }

  return (
    <div className="space-y-8">
      <section className="surface p-5 sm:p-7">
        <p className="label-caps">Upload</p>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Chart, tape, options chain, or ticket. Drop it and the scan ranks
          setups automatically. Sitting out is a valid outcome.
        </p>
        {status ? (
          <p className="mt-3 inline-flex rounded-full border border-white/[0.08] bg-white/[0.04] px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/80">
            {sourceLabel(status.source)}
            {status.vision ? " · vision" : " · desk engines"}
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
            "mt-5 flex min-h-44 w-full flex-col items-center justify-center rounded-xl border border-dashed px-4 py-8 text-center transition-[border-color,background-color,box-shadow]",
            dragging
              ? "border-white/35 bg-white/[0.06] shadow-[inset_0_1px_0_0_hsl(186_40%_90%/0.12)]"
              : "border-white/[0.14] bg-white/[0.02] hover:border-white/25 hover:bg-white/[0.04]",
          )}
        >
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={preview}
              alt="Chart screenshot preview"
              className="max-h-64 w-auto rounded-lg object-contain"
            />
          ) : (
            <>
              <span className="font-mono text-[11px] uppercase tracking-widest text-foreground/80">
                Drop a screenshot — auto-scans setups
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
              className="glass-field mt-2 font-mono uppercase"
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
              className="glass-field mt-2 resize-y"
            />
          </label>
        </div>

        {error ? <p className="mt-4 text-sm text-bearish">{error}</p> : null}

        <button
          type="button"
          disabled={(!file && !symbolHint.trim()) || busy}
          onClick={() => void runScan(file)}
          className="btn-glass mt-5 w-full"
        >
          {busy ? "Scanning setups…" : "Scan again"}
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
      <section className="surface p-5 sm:p-7">
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
        <h2 className="label-caps">Ranked setups</h2>
        <p className="mt-1 mb-4 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/50">
          Best first · analysis, not an order
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          {data.positions.map((position, index) => (
            <PositionCard
              key={`${position.bias}-${position.setup_name}`}
              idea={position}
              rank={index + 1}
            />
          ))}
        </div>
      </section>

      {grounding ? (
        <section className="surface p-5 sm:p-7">
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

function PositionCard({ idea, rank }: { idea: ChartPositionIdea; rank: number }) {
  return (
    <article className={cn("surface p-5", rank === 1 && "border-white/[0.14]")}>
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/55">
            {rank === 1 ? "Best" : `0${rank}`}
          </span>
          <h3 className="label-caps truncate">{idea.setup_name}</h3>
        </div>
        <span className="shrink-0 font-mono text-sm tabular-nums">{idea.confidence.toFixed(0)}</span>
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
