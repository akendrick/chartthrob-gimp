"""GIMP calls for analyzing a scanned ChartThrob chart into a tone-correction
curve.

Ported from `duplicateDocument`, the mode-conversion guard, `patch`,
`getColorAt`, `curveLayer`, and `scanChart` in the original ChartThrob.jsx.
Uses geometry.py (Phase 1) for sampling coordinates and curve_math.py
(Phase 1) for the actual tone math -- this module only issues GIMP calls.

Verified against a real, locally installed GIMP 3.2.4. See
docs/API_MAPPING.md for the full function-by-function mapping and the
resolved "how do we represent a Photoshop-style curve adjustment layer in
GIMP" technical spike (short answer: `Gimp.DrawableFilter` with the
non-deprecated "gimp:curves" operation -- confirmed empirically to apply
correctly for multi-point curves, unlike the deprecated
`Drawable.curves_spline()`, which silently no-ops past 2 control points in
this GIMP version).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("Babl", "0.1")
from gi.repository import Babl, Gegl, Gimp  # noqa: E402

from . import curve_math as cm
from . import geometry as geo

_srgb_format_cache = None


def _srgb_format() -> Babl.Object:
    """Lazily resolves the gamma-encoded sRGB Babl format -- see
    `chart_builder._srgb_format()`'s docstring for why this must stay lazy
    rather than a module-level constant (crashes during GIMP's plugin
    query phase otherwise, confirmed against real GIMP)."""
    global _srgb_format_cache
    if _srgb_format_cache is None:
        _srgb_format_cache = Babl.format("R'G'B'A float")
    return _srgb_format_cache


def _gray_color(value: float) -> Gegl.Color:
    """A `Gegl.Color` for a 0-255 gray value, fully opaque -- same
    linear-vs-gamma pitfall and fix as `chart_builder._gray_color()`
    (see that function's docstring); duplicated here rather than imported
    across modules since it's a two-line helper and this module already
    has its own `_srgb_format()` cache."""
    v = max(0.0, min(1.0, value / 255.0))
    color = Gegl.Color.new("black")
    color.set_rgba_with_space(v, v, v, 1.0, _srgb_format())
    return color


_MODES_NEEDING_RGB_CONVERSION = {
    Gimp.ImageBaseType.GRAY,
    Gimp.ImageBaseType.INDEXED,
}
# The original also guards Photoshop's BITMAP, CMYK, and DUOTONE document
# modes. GIMP's core `ImageBaseType` only has RGB/GRAY/INDEXED -- it has no
# native 1-bit bitmap or duotone base type, and CMYK is not a base image
# type in GIMP (it's handled separately, via color-managed export), so
# there is nothing analogous to guard for those three.


class ChartAnalysisError(Exception):
    """Raised for the failure paths the original reported via `alert()` and
    an early return (no open document, unconvertible mode, curve creation
    failure). Callers that want the original's "just show a message and
    stop" behavior should catch this at the UI layer (Phase 4)."""


@dataclass
class ScanOptions:
    """Ports the scan-analysis toggles from `userDialog()`'s "analyze"
    panel (`gShowSamples`, `gNegate`, `gNoisy`). `gNoisy`'s original effect
    was almost entirely extra `alert()` dialogs -- there's no UI layer here
    yet, so it's omitted until Phase 4 needs it."""

    show_samples: bool = False
    negate: bool = False


# `analyze_chart()`'s result IS `curve_math.build_curve_from_samples()`'s
# result -- the sampling/GIMP layer adds nothing to it, so this is an alias
# rather than a duplicate dataclass with identical fields.
ScanResult = cm.CurveBuildResult


def _pixel_mean_0_255(image: Gimp.Image, layer: Gimp.Layer, bounds: geo.Bounds) -> cm.RGB:
    """Averages the pixels within `bounds` per channel, replacing the
    original's `applyAverage()` (blur the selection flat) + `getColorAt()`
    (read one pixel back out by scanning each channel's histogram for its
    first nonzero bin -- a workaround for Photoshop scripting having no
    direct "read a pixel" call). `Drawable.histogram()`'s `mean` output is
    a direct region average and needs no such workaround; confirmed
    empirically (against real GIMP) to report values in the same 0-255
    sRGB-encoded convention used everywhere else in this codebase.
    """
    image.select_rectangle(
        Gimp.ChannelOps.REPLACE,
        bounds.left,
        bounds.bottom,
        bounds.right - bounds.left,
        bounds.top - bounds.bottom,
    )
    means = []
    for channel in (Gimp.HistogramChannel.RED, Gimp.HistogramChannel.GREEN, Gimp.HistogramChannel.BLUE):
        ok, mean, _std_dev, _median, _pixels, _count, _percentile = layer.histogram(channel, 0.0, 1.0)
        means.append(mean)
    Gimp.Selection.none(image)
    return cm.RGB(red=means[0], green=means[1], blue=means[2])


def sample_patch(
    image: Gimp.Image, layer: Gimp.Layer, i: int, j: int, options: ScanOptions
) -> cm.RGB:
    """Ports `patch(i,j)`."""
    width = image.get_width()
    height = image.get_height()
    bounds = geo.patch_sample_bounds(width, height, i, j)
    color = _pixel_mean_0_255(image, layer, bounds)
    if options.show_samples:
        image.select_rectangle(
            Gimp.ChannelOps.REPLACE,
            bounds.left,
            bounds.bottom,
            bounds.right - bounds.left,
            bounds.top - bounds.bottom,
        )
        red = Gegl.Color.new("black")
        red.set_rgba_with_space(1.0, 0.0, 0.0, 1.0, _srgb_format())
        Gimp.context_set_foreground(red)
        # See chart_builder.out_stroke's docstring: edit_stroke_selection()
        # uses the active brush unless the stroke method is explicitly set
        # to a plain line.
        Gimp.context_set_stroke_method(Gimp.StrokeMethod.LINE)
        Gimp.context_set_line_width(1.0)
        layer.edit_stroke_selection()
        Gimp.Selection.none(image)
    return color


def duplicate_for_sampling(image: Gimp.Image) -> Gimp.Image:
    """Ports `duplicateDocument(origDoc,'ChartThrob_Samples',true)` +
    `samplerDoc.flatten()`. The original's separate `merged` boolean is
    folded into the explicit `.flatten()` call that already followed it
    unconditionally in `scanChart()`."""
    sampler = image.duplicate()
    sampler.flatten()
    return sampler


def ensure_rgb(image: Gimp.Image) -> None:
    """Ports the mode-conversion guard in `scanChart()`. Raises
    `ChartAnalysisError` on failure, matching the original's alert + abort
    (rather than PS's specific "convert to RGB Color" wording, which
    referenced a PS-only menu path)."""
    if image.get_base_type() not in _MODES_NEEDING_RGB_CONVERSION:
        return
    try:
        if not image.convert_rgb():
            raise ChartAnalysisError("Unable to convert the duplicated scan to RGB.")
    except Exception as exc:  # noqa: BLE001 -- mirrors the original's broad catch
        raise ChartAnalysisError(
            "Unable to convert the duplicated scan to RGB. Try converting your scan to "
            "RGB before analyzing it again."
        ) from exc


def apply_curve_to_drawable(
    drawable: Gimp.Drawable, points: List[cm.CurvePoint], name: str, visible: bool = False
) -> Gimp.DrawableFilter:
    """Ports `curveLayer(curvePoints)`.

    RESOLVED TECHNICAL SPIKE (see docs/API_MAPPING.md for the full writeup):
    GIMP has no literal equivalent to Photoshop's draggable Curves
    *adjustment layer*. The closest real analogue is a `Gimp.DrawableFilter`
    running the "gimp:curves" operation, attached non-destructively via
    `append_filter()` (not merged/baked in) and left hidden by default --
    same idea as the original leaving its curve layer hidden
    (`activeLayer.visible = false`). Confirmed empirically against real
    GIMP: `Drawable.curves_spline()` (the direct, seemingly-simpler PDB
    call) is deprecated *and* silently no-ops for curves with more than two
    control points in GIMP 3.2.4 -- a real bug, not a style preference --
    so this uses the filter-based path GIMP's own deprecation notice
    recommends instead. `trc=NON_LINEAR` tells the operation to interpret
    both the curve's points and the image data in the same gamma-encoded
    (non-linear) space this codebase's 0-255 gray values already assume
    everywhere else.

    Unlike Photoshop's curve layer, this filter is bound to the specific
    `drawable` it was created on -- it cannot be dragged onto a different
    image. To reuse a curve on another image, save its `points` (see
    `save_curve`/`load_curve`) and call this function again against the
    new target.
    """
    curve = Gimp.Curve.new()
    curve.set_curve_type(Gimp.CurveType.SMOOTH)
    curve.clear_points()
    for x, y in points:
        curve.add_point(x / 255.0, y / 255.0)

    drawable_filter = Gimp.DrawableFilter.new(drawable, "gimp:curves", name)
    config = drawable_filter.get_config()
    config.set_property("channel", Gimp.HistogramChannel.VALUE)
    config.set_property("trc", Gimp.TRCType.NON_LINEAR)
    config.set_property("curve", curve)
    drawable_filter.update()
    drawable.append_filter(drawable_filter)
    drawable_filter.set_visible(visible)
    return drawable_filter


_IDENTITY_CURVE_POINTS_0_1 = [(0.0, 0.0), (1.0, 1.0)]


def _format_curve_number(value: float) -> str:
    """Matches GIMP's own `.curves` file number formatting, confirmed
    against a real file exported by a real user's GIMP 3.2.4: a value
    that's exactly a whole number is written as a bare integer with no
    decimal point (e.g. the curve's own 0/1 endpoints appear as
    `(points 8 0 0 0.2378... 0.9135... 1 1)` -- bare `0`/`1`, not
    `0.0`/`1.0`), while any other value is written at full float
    precision."""
    if value == int(value):
        return str(int(value))
    return repr(float(value))


def _sample_curve_lut(
    points_0_1, trc: "Gimp.TRCType" = Gimp.TRCType.PERCEPTUAL, num_samples: int = 256
) -> List[float]:
    """Returns the `num_samples`-entry lookup table (0-1 range) GIMP's own
    `"gimp:curves"` SMOOTH-type filter actually produces for the given
    normalized `(x, y)` control points.

    Deliberately NOT via `Gimp.Curve.get_sample()`: confirmed empirically
    against real GIMP that it only works for `Gimp.CurveType.FREE` curves
    -- called on a SMOOTH curve (what this codebase always builds) it
    hits a C-level assertion failure and silently returns `0.0` for every
    input, with only a stderr warning and no Python exception. That would
    have been a very quiet, very wrong bug in an exported curve file.
    Instead, this applies the curve via the same `DrawableFilter`
    mechanism already verified correct in `apply_curve_to_drawable()`, to
    a synthetic `num_samples`-step ramp, and reads back each resulting
    pixel -- reusing only already-verified primitives (gray fills,
    `gimp:curves` `DrawableFilter`, histogram-based pixel reads) rather
    than any new, unverified API surface.
    """
    image = Gimp.Image.new(num_samples, 1, Gimp.ImageBaseType.RGB)
    layer = Gimp.Layer.new(
        image, "ramp", num_samples, 1, Gimp.ImageType.RGB_IMAGE, 100.0, Gimp.LayerMode.NORMAL
    )
    image.insert_layer(layer, None, 0)
    for i in range(num_samples):
        value = 255.0 * i / (num_samples - 1)
        image.select_rectangle(Gimp.ChannelOps.REPLACE, i, 0, 1, 1)
        Gimp.context_set_foreground(_gray_color(value))
        layer.edit_fill(Gimp.FillType.FOREGROUND)
    Gimp.Selection.none(image)

    curve = Gimp.Curve.new()
    curve.set_curve_type(Gimp.CurveType.SMOOTH)
    curve.clear_points()
    for x, y in points_0_1:
        curve.add_point(x, y)
    drawable_filter = Gimp.DrawableFilter.new(layer, "gimp:curves", "curve-export-sampler")
    config = drawable_filter.get_config()
    config.set_property("channel", Gimp.HistogramChannel.VALUE)
    config.set_property("trc", trc)
    config.set_property("curve", curve)
    drawable_filter.update()
    layer.merge_filter(drawable_filter)

    samples: List[float] = []
    for i in range(num_samples):
        image.select_rectangle(Gimp.ChannelOps.REPLACE, i, 0, 1, 1)
        _ok, mean, _sd, _med, _px, _ct, _pct = layer.histogram(Gimp.HistogramChannel.RED, 0.0, 1.0)
        samples.append(mean / 255.0)
    Gimp.Selection.none(image)
    image.delete()
    return samples


def _curve_channel_block(channel_name: str, points_0_1, trc: "Gimp.TRCType") -> str:
    samples = _sample_curve_lut(points_0_1, trc=trc)
    points_flat = [v for point in points_0_1 for v in point]
    points_str = " ".join(_format_curve_number(v) for v in points_flat)
    point_types_str = " ".join(["smooth"] * len(points_0_1))
    samples_str = " ".join(_format_curve_number(v) for v in samples)
    return (
        f"(channel {channel_name})\n"
        f"(curve\n"
        f"    (curve-type smooth)\n"
        f"    (points {len(points_flat)} {points_str})\n"
        f"    (point-types {len(points_0_1)} {point_types_str})\n"
        f"    (n-samples {len(samples)})\n"
        f"    (samples {len(samples)} {samples_str}))\n"
    )


def export_curve_file(
    points: List[cm.CurvePoint], path: str, trc: "Gimp.TRCType" = Gimp.TRCType.PERCEPTUAL
) -> None:
    """Writes the tone-correction curve as a GIMP-native `.curves` settings
    file, loadable via GIMP's Colors > Curves dialog's Import/Open on ANY
    other image -- not just through this plugin or a running GIMP scripting
    session.

    A real feature request, not in the original ChartThrob.jsx (whose own
    "reuse this curve elsewhere" story was Photoshop-only: drag the hidden
    curve layer onto another document, or its own separate save/load via a
    `.csv`-ish file). Also not exposed anywhere in GIMP 3's own PDB --
    confirmed by querying all 1051 registered procedures directly; none of
    them save or load a curve. This file format was reverse-engineered
    from a real file a real user exported from their own GIMP 3.2.4
    Curves dialog, not guessed from a scraped tutorial's ambiguous,
    likely-version-mismatched example (GIMP's Curves dialog moved from a
    much older plain-text format to this self-describing one at some point
    across the 2.x -> 3.x rewrite). The `red`/`green`/`blue`/`alpha`
    channels are written as untouched identity curves, matching how
    GIMP's own dialog exports them when only the Value channel was edited
    -- exactly this plugin's case, since `apply_curve_to_drawable()` only
    ever touches the VALUE channel.
    """
    points_0_1 = [(x / 255.0, y / 255.0) for x, y in points]
    with open(path, "w") as f:
        f.write("# GIMP 'Curves' settings\n\n")
        f.write("(time 0)\n")
        f.write(f"(trc {trc.value_nick})\n")
        f.write(_curve_channel_block("value", points_0_1, trc))
        for channel_name in ("red", "green", "blue", "alpha"):
            f.write(_curve_channel_block(channel_name, _IDENTITY_CURVE_POINTS_0_1, trc))
        f.write("\n# end of 'Curves' settings\n")


def analyze_chart(image: Gimp.Image, options: Optional[ScanOptions] = None) -> ScanResult:
    """Ports `scanChart()`.

    Raises `ChartAnalysisError` for every path the original handled with an
    `alert()` + early return: unconvertible image mode, too few valid curve
    points, a non-monotonic curve, or a curve-filter creation failure.
    """
    if options is None:
        options = ScanOptions()

    sampler = duplicate_for_sampling(image)
    try:
        ensure_rgb(sampler)
        sampler_layer = sampler.get_layers()[0]

        samples: List[cm.RGB] = []
        for j in range(10):
            for i in range(10):
                samples.append(sample_patch(sampler, sampler_layer, i, j, options))
        samples.append(sample_patch(sampler, sampler_layer, 0, 10, options))
    finally:
        if not options.show_samples:
            sampler.delete()

    # All the tone-correction math (normalize, dynamic range, curve-point
    # interpolation, verify, negate) lives in curve_math.py, GIMP-free and
    # unit-tested on its own (tests/golden/, tests/stress/) -- this just
    # hands it real sampled pixels instead of synthetic ones.
    try:
        result = cm.build_curve_from_samples(samples, negate=options.negate)
    except cm.CurveBuildError as exc:
        raise ChartAnalysisError(str(exc)) from exc

    target_layer = image.get_layers()[0]
    try:
        apply_curve_to_drawable(target_layer, result.curve_points, result.curve_name, visible=False)
    except Exception as exc:  # noqa: BLE001 -- mirrors the original's broad catch
        raise ChartAnalysisError(
            "Unable to complete the curve filter. Try converting your scan to RGB and "
            "analyzing it again."
        ) from exc

    return result
