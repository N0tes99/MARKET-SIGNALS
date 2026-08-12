"use client";

import { useCallback, useEffect, useState } from "react";

export type DashboardLayout = "grid" | "list" | "heat";
export type DashboardDensity = "s" | "m";

const LAYOUT_KEY = "se.dashboard.layout";
const DENSITY_KEY = "se.dashboard.density";

function isMobileViewport(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(max-width: 767px)").matches;
}

function readLayout(): DashboardLayout {
  if (typeof window === "undefined") return "grid";
  const stored = window.localStorage.getItem(LAYOUT_KEY);
  if (stored === "chips" || stored === "heat") return "heat";
  if (stored === "grid" || stored === "list") return stored;
  return isMobileViewport() ? "list" : "grid";
}

function readDensity(): DashboardDensity {
  if (typeof window === "undefined") return "m";
  const stored = window.localStorage.getItem(DENSITY_KEY);
  if (stored === "s" || stored === "m") return stored;
  return isMobileViewport() ? "s" : "m";
}

export function useDashboardView() {
  const [layout, setLayoutState] = useState<DashboardLayout>("grid");
  const [density, setDensityState] = useState<DashboardDensity>("m");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setLayoutState(readLayout());
    setDensityState(readDensity());
    setReady(true);
  }, []);

  const setLayout = useCallback((next: DashboardLayout) => {
    setLayoutState(next);
    window.localStorage.setItem(LAYOUT_KEY, next);
  }, []);

  const setDensity = useCallback((next: DashboardDensity) => {
    setDensityState(next);
    window.localStorage.setItem(DENSITY_KEY, next);
  }, []);

  return { layout, density, setLayout, setDensity, ready };
}
