"use client";

import { cn } from "@/lib/utils";
import type { DashboardDensity, DashboardLayout } from "@/hooks/use-dashboard-view";

interface DashboardViewControlsProps {
  layout: DashboardLayout;
  density: DashboardDensity;
  onLayout: (layout: DashboardLayout) => void;
  onDensity: (density: DashboardDensity) => void;
}

const LAYOUTS: { id: DashboardLayout; label: string }[] = [
  { id: "list", label: "List" },
  { id: "chips", label: "Chips" },
  { id: "grid", label: "Grid" },
];

const DENSITIES: { id: DashboardDensity; label: string }[] = [
  { id: "s", label: "S" },
  { id: "m", label: "M" },
];

export function DashboardViewControls({
  layout,
  density,
  onLayout,
  onDensity,
}: DashboardViewControlsProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] pb-4">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        View
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex border border-white/[0.1]">
          {LAYOUTS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onLayout(item.id)}
              className={cn(
                "px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors",
                layout === item.id
                  ? "bg-white/[0.1] text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex border border-white/[0.1]">
          {DENSITIES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onDensity(item.id)}
              className={cn(
                "min-w-[2rem] px-2 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors",
                density === item.id
                  ? "bg-white/[0.1] text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
              title={item.id === "s" ? "Compact" : "Comfortable"}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
