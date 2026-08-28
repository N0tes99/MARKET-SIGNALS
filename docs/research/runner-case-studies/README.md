# Runner case studies (Phase 5–6)

Research notes for the pattern-study set. **Not recommendations.** Live `/radar` Study
replays **structure tape only**: daily bars truncated at each as-of date. Current Yahoo
fundamentals are not written back through history (that would look ahead). 2×/3×/5×/10×
are outcome labels from the path after the fact.

Phase 6 treats this pattern-study set as **holdout**. Threshold search runs on a disjoint
train set (controls + non-famous seed names). Live Radar still uses
`structure_accumulation` = 55 unless a human applies a later change — the tune endpoint
never writes live defaults.

T0 for offset snapshots is the first 2× close after a trough in the first 40% of the
window (or the last bar if 2× never prints). Lead time is calendar days from the first
EARLY list print to that 2× date. Ignition/running stay empty on this replay unless a
**dated** fundamental snapshot exists with `as_of` ≤ the bar.

| Symbol | Why it is on the list |
|--------|------------------------|
| SMCI | Canonical 2023–24 hardware/AI-infrastructure multiple |
| CRDO | High-speed connectivity compounder used in Radar seed + pattern set |
| ALAB | Connectivity / custom-silicon follow-through |
| AAOI | Optics / AI-datacenter beta with violent range |
| LITE | Optical components peer |
| CLS | EMS / datacenter buildout |
| VRT | Power/thermal bottleneck name |
| NBIS | Seed + pattern study (newer listing; 5y window may be short) |

Controls are not assumed. KO and JNJ are fetched as a false-positive
denominator; names that never 2× in the window are the FPR set. Pattern-study
names that 2× are the recall set.

Yahoo 5y daily is the live fetch. Famous 2022–23 legs may sit outside a short listing
or a 5y cut — the engine still measures whatever path arrived, and this file stays the
human label of *why* the name is in the set.
