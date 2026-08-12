/** Binary-partition treemap: larger weights get larger rectangles. */

export type TreemapItem = { id: string; value: number };
export type TreemapCell = TreemapItem & { x: number; y: number; w: number; h: number };

/**
 * Layout in a rectangle matching `aspect` (width / height), then normalize to 0–100%.
 * Passing the real container aspect keeps cells closer to square once stretched on screen.
 */
export function layoutTreemap(items: TreemapItem[], aspect = 1): TreemapCell[] {
  const usable = items
    .map((item) => ({ ...item, value: Math.max(item.value, 0.35) }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value);
  const w = 100 * Math.max(0.4, Math.min(aspect, 5));
  const h = 100;
  return split(usable, 0, 0, w, h).map((cell) => ({
    ...cell,
    x: (cell.x / w) * 100,
    y: (cell.y / h) * 100,
    w: (cell.w / w) * 100,
    h: (cell.h / h) * 100,
  }));
}

function split(items: TreemapItem[], x: number, y: number, w: number, h: number): TreemapCell[] {
  if (items.length === 0) return [];
  if (items.length === 1) {
    return [{ ...items[0], x, y, w, h }];
  }
  const total = items.reduce((sum, item) => sum + item.value, 0);
  let acc = 0;
  let cut = 1;
  const half = total / 2;
  for (let i = 0; i < items.length - 1; i += 1) {
    acc += items[i].value;
    cut = i + 1;
    if (acc >= half) break;
  }
  const left = items.slice(0, cut);
  const right = items.slice(cut);
  const leftSum = left.reduce((sum, item) => sum + item.value, 0);
  const frac = Math.min(0.86, Math.max(0.14, leftSum / total));
  if (w >= h) {
    const lw = w * frac;
    return [...split(left, x, y, lw, h), ...split(right, x + lw, y, w - lw, h)];
  }
  const lh = h * frac;
  return [...split(left, x, y, w, lh), ...split(right, x, y + lh, w, h - lh)];
}
