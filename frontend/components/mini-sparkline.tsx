"use client";

import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";

interface Point {
  t: string;
  close: number;
}

export function MiniSparkline({
  points,
  stroke,
  fill,
}: {
  points: Point[];
  stroke: string;
  fill: string;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
        <YAxis domain={["dataMin", "dataMax"]} hide />
        <Area
          type="monotone"
          dataKey="close"
          stroke={stroke}
          fill={fill}
          strokeWidth={1.5}
          isAnimationActive={false}
          dot={false}
          activeDot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
