# Logo Boot / Hologram Animation — Sketch

Source demo: `logo_boot_holo.html` (boot draw → hologram idle).

## What the demo does

| Layer | Effect | Timing |
|-------|--------|--------|
| Mark | Bottom→top `clip-path` reveal + bright cyan drop-shadow | 0–28% of 5.6s |
| Amber caret | Scan line rides up with the reveal | 0–28%, then fades |
| Scanlines | Cyan horizontal bars fade in after draw | from ~32% |
| Glow floor | Soft cyan ellipse under mark | from ~30% |
| Flicker | Soft opacity / 1px jitter (floor ~0.78 — brand stays readable) | after draw only |
| Terminal line | `SIGNAL_ONLINE` (demo chrome only) | n/a for product |

## Product mapping

Keep the existing **SVG** `SignalMark` (currentColor / void palette). Do **not** ship the demo’s base64 PNG.

```
SignalEngineLogo
  └─ SignalHoloStage (relative)
       ├─ scanlines (lg only)
       ├─ glow floor (lg only)
       ├─ SignalMark (+ clip / flicker)
       └─ amber caret (boot only)
```

| Surface | Mode | Behavior |
|---------|------|----------|
| Dashboard header `size="lg"` | `boot` | One-shot draw + caret, then quiet idle flicker + scanlines |
| Sticky / compact `size="sm"` | `soft` | Short brightness settle only — no caret/scanlines at 20px |
| Unlock / pending | `soft` or `none` | Prefer soft; avoid looping distraction |

**Do not** loop the full boot forever on the live dashboard (demo uses `infinite` for showcase). Boot once per mount, then idle.

## CSS tokens

```css
--logo-holo: #5ff0d0;   /* scan / glow */
--logo-scan: #f0b45f;   /* caret */
```

Respect `prefers-reduced-motion: reduce` → static mark, no caret/scanlines.

## Files

| File | Change |
|------|--------|
| `frontend/app/globals.css` | `@keyframes` + `.logo-holo-*` utilities |
| `frontend/components/signal-engine-logo.tsx` | `SignalHoloStage` + `animation` prop |
| (optional later) | Extract PNG → `public/brand/` only if we need raster art |

## Acceptance

1. Home hero mark boots once, then idles without re-drawing.
2. Compact header stays readable; motion is subtle.
3. Reduced-motion users see a static mark.
4. No new network assets; no huge inline PNG in the React tree.
5. Idle flicker never drops the mark below ~0.78 opacity; scanlines idle around ~0.32.
