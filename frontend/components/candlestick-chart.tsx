"use client";

import { useMemo } from "react";

import type { CandlePoint } from "@/services/api";

interface CandlestickChartProps {
  candles: CandlePoint[];
  upColor?: string;
  downColor?: string;
}

export function CandlestickChart({
  candles,
  upColor = "#8fa88a",
  downColor = "#a67c7c",
}: CandlestickChartProps) {
  const layout = useMemo(() => {
    if (candles.length === 0) return null;

    const highs = candles.map((c) => c.h);
    const lows = candles.map((c) => c.low);
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const pad = (max - min) * 0.06 || Math.abs(max) * 0.01 || 1;
    const yMin = min - pad;
    const yMax = max + pad;
    const span = yMax - yMin || 1;

    const width = 1000;
    const height = 360;
    const padX = 8;
    const padY = 10;
    const innerW = width - padX * 2;
    const innerH = height - padY * 2;
    const slot = innerW / candles.length;
    const bodyW = Math.max(2, Math.min(14, slot * 0.55));

    const y = (price: number) => padY + ((yMax - price) / span) * innerH;

    const bars = candles.map((c, i) => {
      const x = padX + slot * i + slot / 2;
      const bullish = c.c >= c.o;
      const color = bullish ? upColor : downColor;
      const top = y(Math.max(c.o, c.c));
      const bottom = y(Math.min(c.o, c.c));
      const bodyH = Math.max(1, bottom - top);
      return {
        key: `${c.t}-${i}`,
        color,
        wickX: x,
        wickY1: y(c.h),
        wickY2: y(c.low),
        bodyX: x - bodyW / 2,
        bodyY: top,
        bodyW,
        bodyH,
      };
    });

    return { width, height, bars };
  }, [candles, upColor, downColor]);

  if (!layout) return null;

  return (
    <svg
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      className="h-full w-full"
      role="img"
      aria-label="Candlestick chart"
      preserveAspectRatio="none"
    >
      {layout.bars.map((bar) => (
        <g key={bar.key}>
          <line
            x1={bar.wickX}
            x2={bar.wickX}
            y1={bar.wickY1}
            y2={bar.wickY2}
            stroke={bar.color}
            strokeWidth={1.25}
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
          <rect
            x={bar.bodyX}
            y={bar.bodyY}
            width={bar.bodyW}
            height={bar.bodyH}
            fill={bar.color}
            opacity={0.92}
          />
        </g>
      ))}
    </svg>
  );
}
