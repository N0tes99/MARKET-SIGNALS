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
      <p className="label-caps">View</p>
      <div className="flex flex-wrap items-center gap-2">
        <div className="seg-control" role="group" aria-label="Layout">
          {LAYOUTS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onLayout(item.id)}
              data-active={layout === item.id}
              className="seg-control-btn"
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="seg-control" role="group" aria-label="Density">
          {DENSITIES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onDensity(item.id)}
              data-active={density === item.id}
              className={cn("seg-control-btn", "min-w-[2rem]")}
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
