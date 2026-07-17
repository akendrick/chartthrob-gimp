# API Mapping: ChartThrob.jsx → chartthrob-gimp

Function-by-function audit trail. Every original function is listed with its
Python port, and every intentional behavior deviation is called out
explicitly — nothing here should be a silent change. Cross-reference with
`docs/PLAN.md`.

Status key: ✅ ported + tested · ⏳ not started yet · ⛔ not ported (see reason).

**Completeness check (Phase 6):** every one of `ChartThrob.jsx`'s 33
top-level function definitions is accounted for somewhere below, confirmed
by listing them all directly (`awk '/^function |^var .* = function/'`) and
checking each one off — not just the ones that seemed relevant. Two were
missing an explicit row until this pass: `patchStrip` and `showAllGrays`,
both added below. `ps2ga.jsx` (the separate, dead duplicate GA-telemetry
script alongside the main file) is not a `ChartThrob.jsx` function and was
already out of scope per goal G6 (`docs/PLAN.md` 1.1) — noted here for
completeness of this check, not because it needed its own row.

## Phase 1 — Pure math/logic layer (no GIMP dependency)

| Original (`ChartThrob.jsx`) | Port | Status | Deviations |
|---|---|---|---|
| `resetDpi(newDPI)` / initial globals (`gWidth`, `gHeight`, `gXMarg`, `gYMarg`, `gPatch`, `gStripWidth`, `gGradWidth`, `gX21`, `gXGrad`, `gXBar`) | `geometry.ChartLayout.from_dpi()` | ✅ | Globals replaced with an immutable dataclass. No formula changes. |
| DPI floor in `userDialog()` (`if (dv<72) dv=72;`) | `geometry.clamp_dpi()` | ✅ | Extracted as its own function; same threshold (72). |
| `make101`'s per-cell bounds (`boundArray(x,x+gPatch,y,y+gPatch)`) | `ChartLayout.patch_bounds_101(i, j)` | ✅ | None. `j` up to 10 inclusive covers the extra black patch row (`i=0, j=10`), matching the original's separate hardcoded black-patch block. |
| `make21`'s per-step bounds (`boundArray(gX21,x2,y,y+ht+1)`) | `ChartLayout.patch_bounds_21(j)` | ✅ | None. |
| `boundArray(Left,Right,Bottom,Top)` | `geometry.Bounds` (+ `.to_polygon()`) | ✅ | `to_polygon()` reproduces the original's corner order `(L,B),(R,B),(R,T),(L,T)` for later use by chart_builder's selection calls. |
| `make101`'s fill-value formula (`v = floor(0.5+(255-255*(n/100)))`) | `geometry.value_101(n)` | ✅ | The original's separate hardcoded `v=0` for the 101st (black) patch is not special-cased — the same formula naturally yields 0 at n=100. |
| `make21`'s fill-value formula (`v = 255-255*(j/20)`) | `geometry.value_21(j)` | ✅ | None. |
| `gBorderL`, `gBorderR`, `gBorderT`, `gBorderB` (computed once from the initial 300-DPI globals, never recomputed after `resetDpi`) | `geometry.BORDER_LEFT/RIGHT/TOP/BOTTOM` (module-level constants) | ✅ | None — same DPI-invariance reasoning: since they're ratios, recomputing at another DPI would give identical values anyway. |
| `gSampleFraction` (0.55) | `geometry.SAMPLE_FRACTION` | ✅ | None. |
| `patchCenter(i,j)` | `geometry.patch_center(scan_width, scan_height, i, j)` | ✅ | Takes the scanned image's width/height as explicit parameters instead of reading `app.activeDocument`. |
| `selectPatch(i,j)` | `geometry.patch_sample_bounds(scan_width, scan_height, i, j)` | ✅ | Same parameterization change; returns `Bounds` instead of calling into a selection API (that call happens in Phase 3's `chart_analyzer.py`). |
| `toGray(C)` | `curve_math.to_gray(RGB)` | ✅ | Deliberately kept as the flat average, not the commented-out luminance-weighted variant in the original. |
| `grayValues(ColorSamples)` | `curve_math.normalize_paper_tone(samples)` | ✅ | **Zero-paper-channel behavior reproduced exactly, including a sub-case difference from a naive port:** nonzero-sample-over-zero-paper clamps to 255 (matches original's `Infinity` → clamp); **zero-sample-over-zero-paper yields `NaN`** (matches original's `0/0 = NaN`, where `NaN > 255` is `false` in JS so the clamp never fires). A naive `if paper_channel == 0: return 255.0` for both sub-cases would have been wrong — see `test_normalize_paper_tone_zero_paper_and_zero_sample_channel_yields_nan`. The `alert()` for a dark paper tone is replaced with a `dark_paper_warning: bool` field instead of a UI call. |
| `determineDynamicRange(GraySamples)` | `curve_math.compute_dynamic_range(values)` | ✅ | Tie-breaking (`<=`/`>=` → last matching index wins) reproduced with an explicit loop. **Degenerate-fallback direction quirk documented, not fixed:** the fallback ramp runs 0→255 by index position, the *opposite* direction from the non-degenerate branch's 255→0 (lightest-to-darkest) convention. Combined with `find_value_for`'s descending-order expectation, a genuinely degenerate scan will very likely still fail the caller's later "not enough valid curve points" check — flagged for Phase 3 to handle explicitly, not silently masked. |
| `showAllGrays(GraySamples,TheText)` (a debug dialog listing every raw/normalized sample value as text, called twice from inside `determineDynamicRange` when `gNoisy` is set) | *(not ported)* | ⛔ | Its only caller is gated by `gNoisy` ("Excessive Messages"), which was dropped entirely (see Phase 4 table: superseded by this port's actual unit/golden/stress test suites, which inspect these same values far more rigorously than a manual debug dialog ever could). Listed here explicitly for completeness of this audit, not left as a silent gap. |
| `findValueThatGives(origValue, normalizedSamples)` | `curve_math.find_value_for(orig_value, normalized_samples)` | ✅ | Returns `None` instead of `alert()` + `-1`. Added an `L < 2` guard not present in the original (real usage always passes 101 samples; JS produces `Infinity` rather than crashing for `L<2`, Python would raise `ZeroDivisionError` — this guard exists purely so the Python port has a defined answer for an input that never occurs in practice). One branch (`delta == 0`) is retained from the original but is provably unreachable given the loop's own invariants — kept for exact fidelity, marked `# pragma: no cover` with the proof inline. **Does not clamp output to [0,255]** — matches the original's unclamped linear extrapolation; only valid for inputs that actually span the full range (i.e., real output of `compute_dynamic_range`). |
| `verifyCurve(curvePoints)` (monotonicity half) | `curve_math.verify_curve(points)` | ✅ | **Quirk reproduced on purpose:** the original never updates its comparison baseline inside the loop, so it only checks that every point's x-value is ≥ the *first* point's x-value, not full pairwise monotonicity. A curve that rises then dips — as long as it stays above the first point — passes, in both the original and this port. See `test_verify_curve_quirk_dip_above_first_point_still_passes`. |
| `verifyCurve(curvePoints)` (negation half, gated by global `gNegate`) | `curve_math.negate_curve(points)` | ✅ | Split into its own function so negation and monotonicity-checking are independently callable/testable, instead of one function doing both based on a global flag. Net effect on a real call site (`negate_curve(points) if negate else points`) is unchanged. |
| `scanChart()`'s post-sampling orchestration (**added in Phase 5**, moved here from `chart_analyzer.py` -- see Phase 3 table for why) | `curve_math.build_curve_from_samples(samples, negate) -> CurveBuildResult` (raises `CurveBuildError`) | ✅ | Composes `normalize_paper_tone` → `compute_dynamic_range` → the 14-point curve loop → `verify_curve` → `negate_curve`, taking plain `RGB` samples in and returning a `CurveBuildResult` -- no GIMP dependency, so it's exercisable with synthetic samples in `tests/golden/` and `tests/stress/`, not just through a real scanned image. `chart_analyzer.analyze_chart()` calls this with real sampled pixels instead of duplicating the orchestration logic. |

## Phase 2 — Chart builder (GIMP calls)

Verified against a real, locally installed **GIMP 3.2.4**, both by reading
`Gimp-3.0.gir` directly (not assumed from memory -- GIMP 3's API differs
meaningfully from 2.10's PDB naming) and by actually running `build_chart()`
headlessly and inspecting the output PNG. See
`scripts/run_gimp_batch.sh` and `tests/integration/manual_build_chart_smoke.py`.

| Original (`ChartThrob.jsx`) | Port | Status | Deviations |
|---|---|---|---|
| `boundArray(...)` + `selection.select(bd)` | `chart_builder._select(image, bounds)` → `image.select_rectangle(Gimp.ChannelOps.REPLACE, ...)` | ✅ | Takes a `geometry.Bounds` directly. |
| `selection.deselect()` | `chart_builder._deselect(image)` → `Gimp.Selection.none(image)` | ✅ | `Gimp.Selection.*` are module-level functions in GIMP 3's GI bindings, not methods on a selection object -- confirmed via the .gir (`[function]`, not `[method]`). |
| `grayPatch(bd, val)` | `chart_builder.gray_patch(image, layer, bounds, value)` | ✅ | GIMP's `FillType` enum has no arbitrary-RGB member; fills are "foreground/background/white/..." so this sets the foreground color via `Gimp.context_set_foreground()` first, then `layer.edit_fill(Gimp.FillType.FOREGROUND)`. **Real bug found and fixed:** `_gray_color()`'s first implementation used `Gegl.Color.set_rgba(v/255.0, ...)`, which GIMP interprets as *linear light*, not sRGB gamma-encoded -- confirmed empirically that gray value 128 was actually painting as ~188/255 when read back via `Drawable.histogram()`. Every gray value in this codebase (and the original) means the conventional sRGB-encoded 0-255 value, so this now goes through `set_rgba_with_space()` with Babl's `"R'G'B'A float"` (explicitly gamma-encoded) format instead, verified to round-trip exactly (128 in → 128.00 out). Pure black/white were unaffected (gamma curves are identity at both endpoints), which is why this didn't show up until a midtone was checked numerically rather than just viewed. |
| `horizLine(x0,x1,y,val)` | `chart_builder.horiz_line(...)` | ✅ | Delegates to `gray_patch`, same as the original delegates to a fill+select pair inline. |
| `drawGradient(x1,y1,x2,y2,color1,color2)` (raw `ActionDescriptor`/`executeAction('Grdn',...)`, ~100 lines of `charIDToTypeID` boilerplate) | `chart_builder.draw_gradient(...)` → `layer.edit_gradient_fill(...)` | ✅ | **Major simplification, not a behavior change:** GIMP's `edit_gradient_fill` is a single direct call. It takes no color arguments directly -- colors come from the current context (`Gimp.context_set_foreground/background` + `Gimp.context_set_gradient_fg_bg_rgb()` to select the built-in "FG to BG (RGB)" gradient), reproduced here as three calls immediately before the fill. `color1`/`color2` (full `SolidColor` objects in the original) are narrowed to plain 0-255 gray values, since the builder never calls this with anything but grays. Supersampling/dither parameters (`supersample=True, max_depth=3, threshold=0.2, dither=True`) have no equivalent in the original's raw descriptor and were chosen as reasonable GIMP-side smoothing defaults, not derived from the original -- flagged here explicitly per the "no silent changes" rule. |
| `verticalGrad()` | `chart_builder.vertical_grad(...)` | ✅ | None beyond `draw_gradient`'s. |
| `gradLine(x,bottom,top,dv,lv)` | `chart_builder.grad_line(...)` | ✅ | None. |
| `drawBars(xStart,margin)` | `chart_builder.draw_bars(...)` | ✅ | None. |
| `outStroke()` | `chart_builder.out_stroke(...)` | ✅ | `selection.stroke(gBLACK,1)` → `Gimp.context_set_foreground` + `Gimp.context_set_line_width(1.0)` + `layer.edit_stroke_selection()` (stroke width/color are context state in GIMP, not call arguments). **Real bug found and fixed:** `edit_stroke_selection()` strokes with the *active paint method and brush* by default (`Gimp.StrokeMethod.PAINT_METHOD`), not a plain vector line -- `context_set_line_width(1.0)` alone was silently ignored, and the border came out however wide GIMP's default brush happened to be (observed: ~9px, not 1px), swallowing the neighboring patches' edges in the process and corrupting Phase 3's patch sampling near the chart border. Fixed by calling `Gimp.context_set_stroke_method(Gimp.StrokeMethod.LINE)` before the line-width/stroke calls. Found via Phase 3's round-trip test, not by visual inspection -- see Phase 3 section below. |
| `writeText(x,y,userString,val,just)` | `chart_builder.write_text(...)` | ✅ | **Anchor-semantics translation, not a behavior change:** Photoshop's `textItem.position` + `justification` define a horizontal anchor point the text grows from; GIMP positions text layers by top-left corner. `write_text` renders the layer, reads back its width via `Drawable.get_width()`, and computes the equivalent x offset for `LEFT`/`RIGHT`/`CENTER` to reproduce the same visual anchor. **Real bug found by a user, fixed:** the same top-left-vs-anchor mismatch applies *vertically* too -- Photoshop's Y position is baseline-ish (a single line's glyphs mostly extend upward from it), so GIMP's native top-anchored positioning visibly overlapped the grid for the 3x-sized title label (invisible for smaller text, where the discrepancy was too small to notice). Added a `y_anchor="bottom"` option (reads back `Drawable.get_height()`, positions so `y` is the text's bottom edge) and applied it to `buildChart()`'s title label specifically -- other call sites weren't reported as broken and were left unchanged. Font: the original hardcodes `'ArialMT'`; GIMP 3's font lookup keys on `"Family Style"` strings (confirmed against real GIMP: `Gimp.Font.get_by_name("Arial")` → `None`, but `"Arial Regular"` succeeds), so `_resolve_font()` tries a candidate list (`"Arial Regular"`, `"Arial"`, `"Helvetica Regular"`, `"Sans-serif"`) and falls back to GIMP's always-available `"Sans-serif"` generic alias instead of hard-failing like the original's "font not found" dialog loop. Text point-sizes (`20*(72/300)` etc.) are kept as literal points via `Gimp.Unit.point()`, not scaled by the chart's chosen DPI -- see the module docstring for why that's correct (the chart's printed size is DPI-invariant by construction). |
| `patchStrip(colorList,patchSize)` (builds a new document containing a horizontal strip of the given colors) | *(not ported)* | ⛔ | **Dead code in the original**, confirmed by searching every call site in `ChartThrob.jsx`: nothing calls it anywhere in the file. Not a gap in this port -- there is nothing to port. Listed here explicitly so this audit accounts for all 33 of the original's top-level functions, not just the ones that turned out to matter. |
| `make101()` | `chart_builder.make101(...)` | ✅ | Delegates fill values to `geometry.value_101()` (Phase 1) rather than recomputing the formula. |
| `make21()` | `chart_builder.make21(...)` | ✅ | Delegates to `geometry.value_21()`. |
| `buildChart()` | `chart_builder.build_chart(label, layout, options)` | ✅ | `app.documents.add(..., DocumentFill.TRANSPARENT)` + `backGroundColor=WHITE` + `flatten()` → create an opaque `RGB_IMAGE` layer directly and fill it white (equivalent end state, different mechanism). `gChartName` (the original's *document* name) is not handled here -- naming/saving/displaying an image is a Phase 4 (UI/plugin) concern; `build_chart()` returns a bare `Gimp.Image`. |

## Phase 3 — Scan analyzer (GIMP calls)

Verified against real GIMP 3.2.4 both by API inspection and by an actual
headless round-trip proof (build a chart → apply a known synthetic
distortion → analyze it → confirm the recovered curve cancels the
distortion). See `tests/integration/manual_full_roundtrip.py`.

**Resolved technical spike — representing a Photoshop-style curve
adjustment layer in GIMP.** GIMP has no literal equivalent to Photoshop's
draggable Curves adjustment layer. The closest real analogue is a
`Gimp.DrawableFilter` running the `"gimp:curves"` operation, attached
non-destructively via `append_filter()` (not merged/baked in) and left
hidden by default (`set_visible(False)`) -- mirroring the original leaving
its curve layer hidden (`activeLayer.visible = false`). This was reached by
first trying the more obvious-looking `Drawable.curves_spline()`/
`curves_explicit()` PDB calls, which are simpler to call but (a) are
deprecated in favor of `"gimp:curves"` and (b) were found, empirically, to
silently no-op for any curve with more than two control points in this
GIMP version -- confirmed with a direct probe (a 3-point curve applied via
`curves_spline` left the test pixel completely unchanged, while a 2-point
curve worked). Since the real curve always has up to 14 points, this ruled
out `curves_spline` outright regardless of the deprecation notice. The
`Gimp.DrawableFilter` + `"gimp:curves"` path was then verified directly:
a 3-point and a 14-point curve both applied correctly and exactly
(confirmed via `Drawable.histogram()` mean, not visual inspection).
Unlike Photoshop's curve layer, a `DrawableFilter` is bound to the specific
drawable it was created on -- it can't be dragged onto a different image.
The plan's "reuse this curve on another image" need is instead met by
re-running `apply_curve_to_drawable()` with the same `curve_points` against
a new target (the source of truth is the plain point list, not a GIMP
object) -- a save/load helper for that point list is Phase 4/6 scope, not
yet implemented.

| Original (`ChartThrob.jsx`) | Port | Status | Deviations |
|---|---|---|---|
| `duplicateDocument(origDoc,'ChartThrob_Samples',true)` + `samplerDoc.flatten()` | `chart_analyzer.duplicate_for_sampling(image)` | ✅ | `Gimp.Image.duplicate()` + `.flatten()`. The original's separate `merged` boolean argument is folded into the explicit, unconditional `.flatten()` call that already followed it in `scanChart()`. |
| Mode-conversion guard (BITMAP/CMYK/DUOTONE/GRAYSCALE/INDEXEDCOLOR → `changeMode(ChangeMode.RGB)`) | `chart_analyzer.ensure_rgb(image)` | ✅ | GIMP's core `ImageBaseType` only has RGB/GRAY/INDEXED -- no native 1-bit bitmap or duotone base type, and CMYK isn't a base image type in GIMP at all (handled separately, via color-managed export), so only GRAY/INDEXED need guarding. Raises `ChartAnalysisError` instead of `alert()` + early return. |
| `patch(i,j)` (`applyAverage()` blur-the-selection-flat + `getColorAt()` histogram-bin-scan pixel read) | `chart_analyzer.sample_patch(...)` → `_pixel_mean_0_255(...)` using `Drawable.histogram()`'s `mean` output | ✅ | **Confirmed simplification, not a behavior change:** the original's two-step "blur flat, then read one now-uniform pixel back out by scanning each channel's histogram for its first nonzero bin" exists only because Photoshop scripting has no direct region-average call. `Drawable.histogram(channel, 0.0, 1.0)`'s `mean` output is a direct region average and needs no such workaround -- confirmed to report values in the same 0-255 sRGB-encoded convention used everywhere else (a 0.5 linear / 128-sRGB test fill read back as `mean=128.00` through this exact path). |
| `getColorAt(doc,x,y)` | *(subsumed into `_pixel_mean_0_255`)* | ✅ | Not ported separately -- it existed only to work around the same missing-region-average gap `Drawable.histogram()` closes directly. |
| `gShowSamples` outline (`doc.selection.stroke(gRED,1)` inside `patch()`) | `sample_patch(...)`'s `options.show_samples` branch | ✅ | Same `Gimp.StrokeMethod.LINE` fix as `out_stroke()` (see Phase 2 section) applies here too. |
| `curveLayer(curvePoints)` | `chart_analyzer.apply_curve_to_drawable(drawable, points, name, visible)` | ✅ | See the resolved technical spike above. `trc=NON_LINEAR` tells the operation to interpret both the curve's points and the image data in the same gamma-encoded space this codebase's 0-255 gray values already assume everywhere. Raises `ChartAnalysisError` instead of `alert()` + return 0 on failure. |
| `scanChart()`'s post-sampling orchestration (normalize → dynamic range → 14-point curve-building loop → verify → negate) | `curve_math.build_curve_from_samples(samples, negate)` (Phase 1, not Phase 3 -- see Phase 5 note below) | ✅ | **Moved to Phase 1 during Phase 5:** originally inlined directly in `analyze_chart()`, this was extracted into `curve_math.py` so it's unit-testable with plain synthetic `RGB` samples, with no GIMP dependency -- see `tests/golden/` and `tests/stress/`. `analyze_chart()` now just calls it and catches `curve_math.CurveBuildError`, re-raising as `ChartAnalysisError`. Behavior is unchanged (confirmed: re-ran `tests/integration/manual_full_roundtrip.py` and `manual_plugin_e2e.py` after the refactor, identical results both times). |
| `scanChart()`'s `mapToVal>=0` guard when building `curvePoints` | `build_curve_from_samples(...)`'s `if mapped is not None and mapped >= 0:` | ✅ | Faithful to the original checking `>=0` (not just "was a sentinel returned") -- a genuine (if unlikely) negative interpolation result is excluded exactly like the `-1` sentinel, not treated as valid just because it's a real float. |
| `scanChart()`'s `if (i<2)` "not enough samples" guard | `build_curve_from_samples(...)`'s `if len(curve_points) < 2:` | ✅ | Raises `curve_math.CurveBuildError` (`analyze_chart()` re-raises as `ChartAnalysisError`) instead of `alert()` + return -1. **Discovered empirically while writing the Phase 5 stress-test suite:** the degenerate-dynamic-range fallback's direction quirk (Phase 1 table) means this guard is what a genuinely all-identical or reversed scan actually hits -- not a gracefully-produced fallback curve. See `tests/stress/test_stress_cases.py` cases 1, 2b, 7, 9. |
| `verifyCurve(curvePoints)`'s monotonicity check, as called from `scanChart` | `build_curve_from_samples(...)`'s `if not verify_curve(curve_points):` | ✅ | **Provably unreachable via this call site, kept for defensive fidelity anyway:** `curve_points`' x-values here are always `round_half_up(255*j/13)` for `j` in a fixed `range(14)`, filtered but never reordered -- so they're always strictly increasing regardless of how corrupted the input samples are, and `verify_curve` can never return `False` here. Marked `# pragma: no cover` with the proof inline, exactly like `find_value_for`'s already-documented `delta == 0` dead branch. `verify_curve` itself remains directly reachable and tested (`curve_math.verify_curve` called standalone, e.g. from a hand-built `curvePoints` list) -- only *this specific pipeline* can't trigger it. See `tests/stress/test_stress_cases.py` case 10. |
| negation, as called from `scanChart` (gated by global `gNegate`) | `build_curve_from_samples(...)`'s `negate_curve(curve_points) if negate else curve_points` | ✅ | Verify-then-negate call order preserved exactly (negate only runs if verify passed). |
| `scanChart()` overall orchestration | `chart_analyzer.analyze_chart(image, options) -> ScanResult` | ✅ | `ScanResult` is now an alias for `curve_math.CurveBuildResult` (`ScanResult = cm.CurveBuildResult`), not a separate dataclass with duplicate fields -- the sampling/GIMP layer contributes nothing to the result shape that the pure-logic layer doesn't already have. Returns this instead of mutating document/layer state and showing a report dialog -- `scanResultsReport()`'s dialog content becomes a Phase 4 concern, built from this same data. |

**Two real bugs found during Phase 3 verification, both traced back to
Phase 2 code and fixed there** (see the Phase 2 table above for the
in-place fix entries): the linear-vs-sRGB colorspace bug in `_gray_color()`,
and the brush-vs-line-stroke bug in `out_stroke()`. Both were caught by
this phase's round-trip proof, not by visual inspection of the Phase 2
chart -- pure endpoints (black/white) and pixels away from the chart border
happened to be unaffected by either bug, which is exactly why a numeric
check was needed to surface them.

## Phase 4 — UI / plugin registration

**Design decision:** the original's single `userDialog()` adaptively shows
an "Analyze" panel only when a document is open, always shows a "Build"
panel, and dispatches on which button was clicked. Rather than reproduce
that adaptive single-dialog shape, this registers **two** separate GIMP
menu commands -- matching PLAN.md 2.5's own wording ("procedures... mirroring
userDialog()'s choice") and GIMP's own idiom of atomic, single-purpose menu
commands. The adaptive "no document open" behavior is reproduced for free
by GIMP's own menu sensitivity system instead of custom logic: the Analyze
command requires `Gimp.ProcedureSensitivityMask.DRAWABLE`, so GIMP itself
greys it out with no image open, while Build (a plain `Gimp.Procedure`, not
an `ImageProcedure`) is always available -- this is a case where the native
GIMP mechanism is strictly simpler than what the original had to hand-roll.

Both procedures' parameter dialogs are auto-built from declared arguments
via `GimpUi.ProcedureDialog` (see `foggify.py` and
`gradients-save-as-css.py`, both bundled with GIMP, used as verified
reference patterns for the plain-`Procedure` vs `ImageProcedure` callback
signatures) instead of the original's hand-built `ScriptUI` widget tree.

| Original (`ChartThrob.jsx`) | Port | Status | Deviations |
|---|---|---|---|
| `userDialog()`'s "build" panel + its DPI/Numbers/Outlines/Label fields | `python-fu-chartthrob-build` procedure (`build_chart_run`) | ✅ | Plain `Gimp.Procedure` (no image required). `gChartName` (the document name field) is dropped -- see Phase 2/3 notes; there's still nothing to wire it to without a "Save As" step, which stays out of scope. |
| `userDialog()`'s "analyze" panel + its Outline-Sample-Areas/Negate/Excessive-Messages fields | `python-fu-chartthrob-analyze` procedure (`analyze_scan_run`) | ✅ | `Gimp.ImageProcedure` (requires an active image/drawable). `gNoisy` ("Excessive Messages") is dropped -- its original effect was almost entirely extra debug `alert()` popups with no other behavior change, and there's no equivalent debug-dialog need once the code itself is unit-tested (Phase 1) rather than manually stepped through. |
| DPI floor/parse guard in `userDialog()` | `geo.ChartLayout.from_dpi()`'s own `clamp_dpi()` (Phase 1), invoked from `build_chart_run` | ✅ | The dialog's `add_double_argument` range (72-2400) additionally prevents the UI from ever submitting an out-of-range value in the first place, on top of the Phase-1-level clamp. |
| `helpDialog()` | Long-form `set_documentation()` blurb on both procedures (`HELP_TEXT`) | ✅ | **Simplification, not a content loss:** the original needed a hand-built help *window* because ScriptUI dialogs have no built-in documentation display. GIMP already has one (Procedure Browser, dialog description), so this reuses it instead of building a redundant custom window. Content (the numbered step list) is carried over near-verbatim. |
| `scanResultsReport()` (including its shoulder/toe exposure-suggestion logic) | `_report_message(result)` + `Gimp.message()` | ✅ | Reads `ScanResult.dynamic_range.max_index`/`min_index` (Phase 3) as the `gLightestSample`/`gDarkestSample` equivalents; same shoulder/toe comparison thresholds (`1.5x`, `>5`) preserved exactly. Rendered as a plain message instead of a custom report dialog window. |
| `main()` (mode dispatch + ruler-unit save/restore) | `Gimp.PlugIn.do_query_procedures`/`do_create_procedure` registration + each callback | ✅ | The original's ruler-unit save/restore (`app.preferences.rulerUnits`) has no equivalent need here -- this port always works in absolute pixel coordinates internally (Phase 1's `geometry.py`) rather than reading/depending on a global, user-configurable ruler-unit preference. |
| Google Analytics telemetry (`GaEmitter`, `gTracker.sendPayload(...)` calls scattered through `main()`/`scanChart()`/`scanResultsReport()`) | *(intentionally not ported)* | ✅ | Per PLAN.md goal G6. No phone-home of any kind anywhere in this plugin. |

**Real bug found and fixed during verification:** `Gimp.Display.new(image)`
raises (`TypeError: constructor returned NULL`) when there's no display
server to attach a window to -- confirmed when driving the build procedure
straight through the PDB in headless batch mode. Wrapped in a `try/except
TypeError` in `build_chart_run`, since the image itself is still created
and valid either way; a real interactive GIMP session never hits this path
in the first place. Also required guarding the plugin file's bottom-level
`Gimp.main(ChartThrobPlugIn.__gtype__, sys.argv)` call behind
`if __name__ == "__main__":` -- GIMP always invokes plugin files directly
(so this is a no-op change for real usage), but the bare call blocked
forever on `Gimp.main()`'s wire-protocol handshake when the file was
imported by a test harness with argv that isn't a real GIMP-supplied
invocation.

**Known verification-harness limitation (not a plugin defect):** GIMP
3.2.4's Python bindings do not support setting a `GimpCoreObjectArray`
-typed `ProcedureConfig` property (the implicit "drawables" argument every
`ImageProcedure` has) via generic `set_property()` -- confirmed with both a
list and a tuple, both raising an identical `TypeError`. This blocks
driving `python-fu-chartthrob-analyze` through a fully PDB-marshaled call
in a headless script; it does not affect real usage, since GIMP's own menu
dispatch supplies `image`/`drawables` as native arguments directly (the
same way `foggify.py`, bundled with GIMP, receives them). Worked around in
`tests/integration/manual_plugin_e2e.py` by calling the real
`analyze_scan_run()` function directly with a real image/drawable and a
minimal stand-in config object, rather than reimplementing or skipping the
check.

**Installed and verified against a real, locally installed GIMP 3.2.4**
(symlinked `plugin/chartthrob-plugin` into the user's GIMP 3.2 plug-ins
directory): both procedures register with the PDB, the build procedure
produces a correctly-sized image through the real PDB call path, and the
analyze procedure correctly attaches a hidden "Print Curve" filter. See
`tests/integration/manual_plugin_e2e.py`.
