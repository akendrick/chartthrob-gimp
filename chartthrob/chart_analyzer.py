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
