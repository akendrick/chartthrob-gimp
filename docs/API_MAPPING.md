# API Mapping: ChartThrob.jsx → chartthrob-gimp

Function-by-function audit trail. Every original function is listed with its
Python port, and every intentional behavior deviation is called out
explicitly — nothing here should be a silent change. Cross-reference with
`docs/PLAN.md`.

Status key: ✅ ported + tested · ⏳ not started yet.

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
| `findValueThatGives(origValue, normalizedSamples)` | `curve_math.find_value_for(orig_value, normalized_samples)` | ✅ | Returns `None` instead of `alert()` + `-1`. Added an `L < 2` guard not present in the original (real usage always passes 101 samples; JS produces `Infinity` rather than crashing for `L<2`, Python would raise `ZeroDivisionError` — this guard exists purely so the Python port has a defined answer for an input that never occurs in practice). One branch (`delta == 0`) is retained from the original but is provably unreachable given the loop's own invariants — kept for exact fidelity, marked `# pragma: no cover` with the proof inline. **Does not clamp output to [0,255]** — matches the original's unclamped linear extrapolation; only valid for inputs that actually span the full range (i.e., real output of `compute_dynamic_range`). |
| `verifyCurve(curvePoints)` (monotonicity half) | `curve_math.verify_curve(points)` | ✅ | **Quirk reproduced on purpose:** the original never updates its comparison baseline inside the loop, so it only checks that every point's x-value is ≥ the *first* point's x-value, not full pairwise monotonicity. A curve that rises then dips — as long as it stays above the first point — passes, in both the original and this port. See `test_verify_curve_quirk_dip_above_first_point_still_passes`. |
| `verifyCurve(curvePoints)` (negation half, gated by global `gNegate`) | `curve_math.negate_curve(points)` | ✅ | Split into its own function so negation and monotonicity-checking are independently callable/testable, instead of one function doing both based on a global flag. Net effect on a real call site (`negate_curve(points) if negate else points`) is unchanged. |

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
| `grayPatch(bd, val)` | `chart_builder.gray_patch(image, layer, bounds, value)` | ✅ | GIMP's `FillType` enum has no arbitrary-RGB member; fills are "foreground/background/white/..." so this sets the foreground color via `Gimp.context_set_foreground()` first, then `layer.edit_fill(Gimp.FillType.FOREGROUND)`. |
| `horizLine(x0,x1,y,val)` | `chart_builder.horiz_line(...)` | ✅ | Delegates to `gray_patch`, same as the original delegates to a fill+select pair inline. |
| `drawGradient(x1,y1,x2,y2,color1,color2)` (raw `ActionDescriptor`/`executeAction('Grdn',...)`, ~100 lines of `charIDToTypeID` boilerplate) | `chart_builder.draw_gradient(...)` → `layer.edit_gradient_fill(...)` | ✅ | **Major simplification, not a behavior change:** GIMP's `edit_gradient_fill` is a single direct call. It takes no color arguments directly -- colors come from the current context (`Gimp.context_set_foreground/background` + `Gimp.context_set_gradient_fg_bg_rgb()` to select the built-in "FG to BG (RGB)" gradient), reproduced here as three calls immediately before the fill. `color1`/`color2` (full `SolidColor` objects in the original) are narrowed to plain 0-255 gray values, since the builder never calls this with anything but grays. Supersampling/dither parameters (`supersample=True, max_depth=3, threshold=0.2, dither=True`) have no equivalent in the original's raw descriptor and were chosen as reasonable GIMP-side smoothing defaults, not derived from the original -- flagged here explicitly per the "no silent changes" rule. |
| `verticalGrad()` | `chart_builder.vertical_grad(...)` | ✅ | None beyond `draw_gradient`'s. |
| `gradLine(x,bottom,top,dv,lv)` | `chart_builder.grad_line(...)` | ✅ | None. |
| `drawBars(xStart,margin)` | `chart_builder.draw_bars(...)` | ✅ | None. |
| `outStroke()` | `chart_builder.out_stroke(...)` | ✅ | `selection.stroke(gBLACK,1)` → `Gimp.context_set_foreground` + `Gimp.context_set_line_width(1.0)` + `layer.edit_stroke_selection()` (stroke width/color are context state in GIMP, not call arguments). |
| `writeText(x,y,userString,val,just)` | `chart_builder.write_text(...)` | ✅ | **Anchor-semantics translation, not a behavior change:** Photoshop's `textItem.position` + `justification` define an anchor point the text grows from; GIMP positions text layers by top-left corner. `write_text` renders the layer, reads back its width via `Drawable.get_width()`, and computes the equivalent offset for `LEFT`/`RIGHT`/`CENTER` to reproduce the same visual anchor. Font: the original hardcodes `'ArialMT'`; GIMP 3's font lookup keys on `"Family Style"` strings (confirmed against real GIMP: `Gimp.Font.get_by_name("Arial")` → `None`, but `"Arial Regular"` succeeds), so `_resolve_font()` tries a candidate list (`"Arial Regular"`, `"Arial"`, `"Helvetica Regular"`, `"Sans-serif"`) and falls back to GIMP's always-available `"Sans-serif"` generic alias instead of hard-failing like the original's "font not found" dialog loop. Text point-sizes (`20*(72/300)` etc.) are kept as literal points via `Gimp.Unit.point()`, not scaled by the chart's chosen DPI -- see the module docstring for why that's correct (the chart's printed size is DPI-invariant by construction). |
| `make101()` | `chart_builder.make101(...)` | ✅ | Delegates fill values to `geometry.value_101()` (Phase 1) rather than recomputing the formula. |
| `make21()` | `chart_builder.make21(...)` | ✅ | Delegates to `geometry.value_21()`. |
| `buildChart()` | `chart_builder.build_chart(label, layout, options)` | ✅ | `app.documents.add(..., DocumentFill.TRANSPARENT)` + `backGroundColor=WHITE` + `flatten()` → create an opaque `RGB_IMAGE` layer directly and fill it white (equivalent end state, different mechanism). `gChartName` (the original's *document* name) is not handled here -- naming/saving/displaying an image is a Phase 4 (UI/plugin) concern; `build_chart()` returns a bare `Gimp.Image`. |

## Phase 3 — Scan analyzer (GIMP calls)

⏳ Not started.

## Phase 3 — Scan analyzer (GIMP calls)

⏳ Not started.

## Phase 4 — UI / plugin registration

⏳ Not started.
