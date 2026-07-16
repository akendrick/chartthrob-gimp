# Changelog

## [0.1.0] — 2026-07-16

Initial GIMP 3 port of ChartThrob. Full technical detail and rationale for
every item below lives in `docs/API_MAPPING.md` (function-by-function) and
`docs/PLAN.md` section 3 (narrative, with how each was found).

### Added

- Two GIMP menu commands replacing the original's single adaptive dialog:
  **File → Create → ChartThrob → Build Chart...** (always available) and
  **Colors → ChartThrob → Analyze Scan...** (enabled once an image is
  open) — GIMP's own menu sensitivity now handles the "is a document
  open" logic the original had to check manually.
- A tone-correction curve is attached to the analyzed image as a hidden,
  non-destructive `Gimp.DrawableFilter` ("Print Curve" / "Negative Curve"
  if negated) instead of Photoshop's adjustment layer, which GIMP has no
  direct equivalent of.

### Changed (deliberate behavior/mechanism differences from the original)

- **Gradient fills, patch fills, and stroke outlines** use direct GIMP
  calls (`edit_gradient_fill`, `edit_fill`, `edit_stroke_selection`)
  instead of ~100 lines of raw Photoshop `ActionDescriptor`/`executeAction`
  plumbing the original needed for the same effect.
- **Patch color sampling** uses `Drawable.histogram()`'s direct region
  mean instead of the original's "blur the selection flat, then read one
  pixel back out by scanning each channel's histogram for its first
  nonzero bin" — a workaround that existed only because Photoshop
  scripting has no direct region-average call.
- **Font selection** falls back through a candidate list (`"Arial
  Regular"` → `"Arial"` → `"Helvetica Regular"` → `"Sans-serif"`) instead
  of hard-failing with a "font not found" dialog when the original's exact
  font isn't installed.
- **Text sizing** stays in physical points (`Gimp.Unit.point()`), matching
  the original's own convention — not scaled by the chart's chosen DPI,
  since the chart's printed size is DPI-invariant by construction.

### Removed

- **All telemetry.** The original's Google Analytics Measurement Protocol
  client (and its dead duplicate, `ps2ga.jsx`) is not ported. This plugin
  makes no network requests of any kind.
- **"Excessive Messages" debug toggle** (`gNoisy`) and its associated debug
  dialogs (`showAllGrays`). Superseded by this port's actual automated test
  suite (unit, property, golden-vector, and stress tests), which inspects
  the same intermediate values far more rigorously than a manual debug
  popup ever could.
- **Document/chart naming** (`gChartName`). Nothing to wire it to without a
  "Save As" step, which is out of scope for this release.

### Known limitations / preserved original quirks

These are not bugs in this port — they're either inherent to the original
algorithm (preserved deliberately, for fidelity) or genuine gaps in GIMP
itself that this port works around rather than papers over. Full detail in
`docs/PLAN.md` section 3.2 and `docs/API_MAPPING.md`.

- A single corrupted or dust-specked patch in a scan can silently distort
  roughly half of the recovered curve's range, rather than being detected
  and flagged — this is how the original's algorithm has always behaved.
- A genuinely blank, flat, or reversed/negative scan raises an error
  ("not enough samples") rather than gracefully producing a fallback
  curve — also original behavior, now backed by a test that pins it.
- The tone-correction curve is bound to the specific image it was applied
  to; unlike Photoshop's curve layers, it can't be dragged onto a
  different image in GIMP's UI. Reuse it on another image by re-running
  Analyze with the same source curve's points, or (same-session only)
  reusing the same `Gimp.Curve` object programmatically.
- GIMP 3.2.4's `Drawable.curves_spline()`/`curves_explicit()` PDB calls are
  deprecated and were found to silently do nothing for curves with more
  than two control points — this plugin uses the non-deprecated
  `Gimp.DrawableFilter` + `"gimp:curves"` path instead, which was verified
  to work correctly for the full 14-point curve.

### Testing

- 78 automated tests (unit, property-based, golden-vector, stress),
  100% line coverage on the pure math/logic layer, runnable with plain
  `pytest` — no GIMP installation required.
- 5 additional integration scripts verified against a real, locally
  installed GIMP 3.2.4 (not yet wired into automated CI — see
  `docs/PLAN.md` section 3.3), covering: chart generation, the full
  build→distort→analyze round-trip, plugin registration end-to-end, and
  non-RGB image-mode conversion.
