# Changelog

## [0.2.1] — 2026-10-12

- Published at <https://github.com/akendrick/chartthrob-gimp> under the
  MIT License (the GIMP port's own code; see the README's licensing note).
- Unit tests run on GitHub Actions for every push.

## [0.2.0] — 2026-09-23

### Distribution

- Release builds are now self-contained: `scripts/build_release.sh` bundles
  the `chartthrob` package inside the plugin folder, so a plain copy into
  GIMP's plug-ins directory works (previously the plugin only found its
  package through a symlink into a full checkout).
- `scripts/install.sh` installs (or `--link`s, or `--uninstall`s) for macOS
  and Linux, with `--gimp-version` / `--plugins-dir` overrides.
- Integration scripts no longer contain machine-specific paths;
  `scripts/run_gimp_batch.sh` exports `CHARTTHROB_ROOT` and finds the GIMP
  binary on macOS and Linux (preferring `gimp-console`, since the GUI binary
  crashes in `-i` mode on recent macOS).

### Changed

- **"Not enough samples had valid values to estimate a curve" now explains
  why.** A real user hit this exact error analyzing a real scan; the
  message previously gave no way to tell whether the cause was a
  near-flat measured tonal range (e.g. the crop includes background
  outside the chart, a low-contrast print, or an auto-levels/auto-contrast
  step flattened the scan) or an unusually dark paper-tone reading (often
  an inverted/negative scan, or a crop whose top-left corner isn't
  actually the chart's lightest patch) without reading source code. The
  error now names the likely cause(s) directly, plus the raw measured
  numbers either way.

### Added

- **Padding option** on the Build Chart dialog, requested by a real user
  of this port -- not in the original ChartThrob.jsx. Off by default
  (identical behavior to before). When enabled, adds a solid white border
  of a user-chosen pixel width (default 40px) around the finished chart.
  When the chart is later inverted for a digital negative, this border
  stays a firm, fully unexposed area, giving contact printers a uniform
  margin to isolate the print from its support material. The pixel-width
  field is only enabled once padding is turned on (`GimpUi.ProcedureDialog
  .set_sensitive()`, bound declaratively to the padding toggle rather than
  managed by hand). See `chartthrob.chart_builder.add_padding()` and
  `docs/API_MAPPING.md`'s Phase 2 section for how the border itself is
  produced (canvas resize + a full-size white layer behind the existing
  content, verified against real GIMP rather than assumed).

- **Curve file export** on the Analyze Scan dialog, requested by a real
  user of this port -- not in the original ChartThrob.jsx, and not
  exposed anywhere in GIMP's own scripting API (confirmed by querying all
  1051 registered PDB procedures directly; none save or load a curve).
  Optional (leave the file field empty to skip, matching prior behavior).
  When set, writes the analyzed curve as a GIMP-native `.curves` settings
  file -- loadable via **Colors > Curves > Import/Open** on *any* image,
  not just through this plugin, closing the "reuse this curve on other
  images" gap the hidden `DrawableFilter` alone doesn't solve across
  separate GIMP sessions. The file format was reverse-engineered from a
  real file a real user exported from their own GIMP 3.2.4 Curves dialog
  (not guessed from an older, likely-version-mismatched tutorial format),
  and its 256-entry sample table is generated using GIMP's own curve
  engine (applying the curve to a synthetic ramp and reading back the
  result) rather than reimplementing GIMP's spline interpolation in
  Python. See `chartthrob.chart_analyzer.export_curve_file()` and
  `docs/API_MAPPING.md`'s Phase 3 section for the full field-by-field
  format mapping. **Confirmed working end-to-end by a real user**: a file
  exported through the actual plugin path (build chart, simulate a real
  print distortion, analyze, export) was imported via GIMP's own Colors >
  Curves > Import and showed the correctly distorted curve shape -- the
  one step that couldn't be verified without GUI access.

### Fixed

- **"Outline Sample Areas" showed nothing.** It kept the outlined working
  copy of the scan but never opened a window for it. It now opens it (best
  effort; skipped when there's no display, e.g. headless runs).
- **Chart title overlapped the top row of patches.** Found by a real user
  running the plugin. `write_text()` positions text layers by their
  top-left corner (GIMP's native behavior); Photoshop's `textItem.position`
  is closer to a baseline anchor, where a single line's glyphs mostly
  extend *upward* from it. That mismatch was invisible for small text
  (per-patch numbers, the credits block) but became an obvious overlap for
  the 3x-sized title label sitting just above the grid. Added a
  `y_anchor="bottom"` option to `write_text()` (reads back the rendered
  text height and positions so `y` is the bottom of the text, not the
  top) and applied it to the title label specifically.

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
