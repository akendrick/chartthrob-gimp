"""GIMP drawing calls for building ChartThrob's printable calibration chart.

Ported from `make101`, `make21`, `drawGradient`/`verticalGrad`, `drawBars`,
`horizLine`, `gradLine`, `writeText`, `outStroke`, and `buildChart` in the
original ChartThrob.jsx. All layout math lives in geometry.py (Phase 1) --
this module only issues GIMP calls against a real `Gimp.Image`.

Verified against GIMP 3.2.4's actual GObject-Introspection API
(Gimp-3.0.gir) rather than assumed from memory -- GIMP 3's API differs
meaningfully from 2.10's PDB naming. See docs/API_MAPPING.md.

TEXT SIZING NOTE: the original specifies all text sizes in POINTS (a fixed
physical unit) via formulas like `20*(72/300)`, and never scales them by the
chart's chosen DPI (`gDPI`) -- only pixel *positions* get scaled by DPI. This
isn't an oversight: the chart's printed width is DPI-invariant by
construction (`gWidth/gDPI` is always 4 inches, since `gWidth` itself scales
proportionally with `gDPI` -- see geometry.ChartLayout), so a fixed physical
point size is exactly what keeps text proportioned correctly on the printed
page regardless of pixel resolution. This port keeps that same fixed-point
convention rather than pixel-scaling text size by `dpi_scale`.
"""
from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gegl, Gimp  # noqa: E402

from . import geometry as geo
from .geometry import Bounds, ChartLayout

FONT_CANDIDATES = ("Arial Regular", "Arial", "Helvetica Regular", "Sans-serif")
# The original hardcodes 'ArialMT'; per its own FAQ, it never actually used
# "Myriad" despite early confusion, so "Arial" is the right family to chase.
# GIMP 3's font database keys on "Family Style" (e.g. "Arial Regular"), not
# the bare family name -- confirmed against a real headless GIMP 3.2.4,
# where `Gimp.Font.get_by_name("Arial")` returns None but
# `Gimp.Font.get_by_name("Arial Regular")` succeeds. Since Arial isn't
# guaranteed to be installed on every OS this plugin might run on (G4:
# cross-platform), this list falls through to "Sans-serif", one of GIMP's
# always-available built-in generic aliases, rather than hard-failing like
# the original's "font not found" dialog loop.


def _resolve_font() -> Gimp.Font:
    for name in FONT_CANDIDATES:
        font = Gimp.Font.get_by_name(name)
        if font is not None:
            return font
    raise RuntimeError(
        f"None of the candidate fonts {FONT_CANDIDATES} were found -- "
        "not even the 'Sans-serif' built-in alias, which should always exist."
    )

VERSION = "1.15"  # carried from the original's gVersion, for the on-chart
# credit text only -- unrelated to this package's own __version__.
CHART_TITLE = f"ChartThrob V{VERSION}"

_POINTS_PER_PIXEL_AT_300DPI = 72.0 / 300.0
LABEL_POINT_SIZE = 20 * _POINTS_PER_PIXEL_AT_300DPI  # per-patch numeric labels
CREDIT_POINT_SIZE = 16 * _POINTS_PER_PIXEL_AT_300DPI  # title/credits block
BIG_LABEL_POINT_SIZE = CREDIT_POINT_SIZE * 3.0  # top banner label


class ChartOptions:
    """Ports the two toggles from `userDialog()`'s "build" panel (`gText`,
    `gLines`). `gDPI`/`gChartName`/`gLabel` are handled separately -- DPI via
    `ChartLayout`, name/label as explicit `build_chart()` parameters."""

    def __init__(self, numbers: bool = False, outlines: bool = True) -> None:
        self.numbers = numbers
        self.outlines = outlines


def _gray_color(value: float) -> Gegl.Color:
    """A `Gegl.Color` for a 0-255 gray value, fully opaque."""
    v = max(0.0, min(1.0, value / 255.0))
    color = Gegl.Color.new("black")
    color.set_rgba(v, v, v, 1.0)
    return color


def _select(image: Gimp.Image, b: Bounds) -> None:
    image.select_rectangle(
        Gimp.ChannelOps.REPLACE, b.left, b.bottom, b.right - b.left, b.top - b.bottom
    )


def _deselect(image: Gimp.Image) -> None:
    Gimp.Selection.none(image)


def gray_patch(image: Gimp.Image, layer: Gimp.Layer, bounds: Bounds, value: float) -> None:
    """Ports `grayPatch(bd, val)`."""
    _select(image, bounds)
    Gimp.context_set_foreground(_gray_color(value))
    layer.edit_fill(Gimp.FillType.FOREGROUND)
    _deselect(image)


def horiz_line(
    image: Gimp.Image, layer: Gimp.Layer, x0: float, x1: float, y: float, value: float
) -> None:
    """Ports `horizLine(x0,x1,y,val)`."""
    gray_patch(image, layer, Bounds(left=x0, right=x1, bottom=y - 1, top=y + 1), value)


def draw_gradient(
    image: Gimp.Image,
    layer: Gimp.Layer,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    value1: float,
    value2: float,
) -> None:
    """Ports `drawGradient(x1,y1,x2,y2,color1,color2)`. The original always
    calls this with grayscale colors, so this takes 0-255 gray values
    directly rather than full SolidColor objects.

    `value1` paints at (x1, y1) and `value2` paints at (x2, y2), matching
    the original's `From`/`To` gradient-stop semantics -- reproduced here
    via `context_set_foreground(value1)` + `context_set_background(value2)`
    + the built-in "FG to BG (RGB)" gradient, since GIMP's
    `edit_gradient_fill` takes no direct color arguments.
    """
    Gimp.context_set_foreground(_gray_color(value1))
    Gimp.context_set_background(_gray_color(value2))
    Gimp.context_set_gradient_fg_bg_rgb()
    layer.edit_gradient_fill(
        Gimp.GradientType.LINEAR,
        0.0,  # offset
        True,  # supersample
        3,  # supersample_max_depth
        0.2,  # supersample_threshold
        True,  # dither
        x1,
        y1,
        x2,
        y2,
    )


def vertical_grad(image: Gimp.Image, layer: Gimp.Layer, layout: ChartLayout) -> None:
    """Ports `verticalGrad()`: a black-to-white gradient bar, black at the
    bottom (y=height) rising to white at the top (y=0)."""
    b = Bounds(left=layout.x_grad, right=layout.x_grad + layout.grad_width, bottom=0, top=layout.height)
    _select(image, b)
    xc = layout.x_grad + layout.grad_width / 2.0
    draw_gradient(image, layer, xc, layout.height, xc, 0, 0.0, 255.0)
    _deselect(image)


def grad_line(
    image: Gimp.Image,
    layer: Gimp.Layer,
    x: float,
    bottom: float,
    top: float,
    dark_value: float,
    light_value: float,
) -> None:
    """Ports `gradLine(x,bottom,top,dv,lv)`: a thin vertical gradient
    stroke, light at `bottom` fading to dark at `top`."""
    b = Bounds(left=x - 1, right=x + 1, bottom=bottom, top=top)
    _select(image, b)
    draw_gradient(image, layer, x, bottom, x, top, light_value, dark_value)
    _deselect(image)


def draw_bars(
    image: Gimp.Image, layer: Gimp.Layer, layout: ChartLayout, x_start: float, margin: float
) -> None:
    """Ports `drawBars(xStart, margin)`: a black bar with a white swatch in
    its upper half, used as a rough by-eye tone reference."""
    gray_patch(image, layer, Bounds(left=x_start, right=layout.width, bottom=0, top=layout.height), 0.0)
    top = margin + (layout.height - margin) / 2.0
    gray_patch(
        image, layer, Bounds(left=x_start, right=layout.width - margin, bottom=margin, top=top), 255.0
    )


def out_stroke(image: Gimp.Image, layer: Gimp.Layer, layout: ChartLayout) -> None:
    """Ports `outStroke()`: a 1px black border around the whole chart."""
    _select(image, Bounds(left=0, right=layout.width, bottom=0, top=layout.height))
    Gimp.context_set_foreground(_gray_color(0.0))
    Gimp.context_set_line_width(1.0)
    layer.edit_stroke_selection()
    _deselect(image)


def write_text(
    image: Gimp.Image,
    x: float,
    y: float,
    text: str,
    value: float,
    justification: Gimp.TextJustification = Gimp.TextJustification.LEFT,
    point_size: float = LABEL_POINT_SIZE,
) -> Gimp.TextLayer:
    """Ports `writeText(x,y,userString,val,just)`.

    Photoshop's `textItem.position` + `justification` together define an
    *anchor point* (x stays fixed; the text grows left/right/centered from
    it). GIMP positions text layers by their top-left corner instead, so
    this renders the layer first, reads back its width, and computes the
    equivalent offset -- reproducing the same anchor behavior.
    """
    font = _resolve_font()
    layer = Gimp.TextLayer.new(image, text, font, point_size, Gimp.Unit.point())
    image.insert_layer(layer, None, 0)
    layer.set_color(_gray_color(value))
    layer.set_justification(justification)
    width = layer.get_width()
    if justification == Gimp.TextJustification.RIGHT:
        offset_x = x - width
    elif justification == Gimp.TextJustification.CENTER:
        offset_x = x - width / 2.0
    else:
        offset_x = x
    layer.set_offsets(int(round(offset_x)), int(round(y)))
    return layer


def make101(
    image: Gimp.Image, layer: Gimp.Layer, layout: ChartLayout, options: ChartOptions
) -> Gimp.Layer:
    """Ports `make101()`: the 10x10 patch grid plus one extra pure-black
    patch. Returns the current layer (re-flattened whenever text labels
    were baked in, matching the original's repeated
    `app.activeDocument.flatten()` calls)."""
    n = 0
    p = 1
    for j in range(10):
        for i in range(10):
            value = geo.value_101(n)
            b = layout.patch_bounds_101(i, j)
            gray_patch(image, layer, b, value)
            if options.numbers:
                text_value = 255.0 if value < 128 else 0.0
                write_text(image, b.left + 6, b.bottom + 20, f"{n}%", text_value, Gimp.TextJustification.LEFT)
                write_text(
                    image, b.right - 6, b.bottom + 20, str(255 - value), text_value, Gimp.TextJustification.RIGHT
                )
                if n % 5 == 0:
                    write_text(image, b.left + 6, b.top - 6, str(p), text_value, Gimp.TextJustification.LEFT)
                    p += 1
                layer = image.flatten()
            n += 1

    b = layout.patch_bounds_101(0, 10)
    gray_patch(image, layer, b, 0.0)
    if options.numbers:
        write_text(image, b.left + 6, b.bottom + 20, f"{n}%", 255.0, Gimp.TextJustification.LEFT)
        write_text(image, b.right - 6, b.bottom + 20, "255", 255.0, Gimp.TextJustification.RIGHT)
        write_text(image, b.left + 6, b.top - 6, str(p), 255.0, Gimp.TextJustification.LEFT)
        layer = image.flatten()

    if options.outlines:
        y = layout.y_marg
        for i in range(11):
            x = layout.x_marg + i * layout.patch
            v = 55 + 145 * (i / 10.0)
            if i < 2:
                grad_line(image, layer, x, layout.y_marg - 1, layout.y_marg + 11 * layout.patch + 1, 55.0, 200.0)
            else:
                grad_line(image, layer, x, layout.y_marg - 1, layout.y_marg + 10 * layout.patch + 1, 55.0, 200.0)
            y = layout.y_marg + i * layout.patch
            horiz_line(image, layer, layout.x_marg - 1, layout.x_marg + 10 * layout.patch + 1, y, v)
        horiz_line(image, layer, layout.x_marg - 1, layout.x_marg + layout.patch + 1, y + layout.patch, v)

    return layer


def make21(
    image: Gimp.Image, layer: Gimp.Layer, layout: ChartLayout, options: ChartOptions
) -> Gimp.Layer:
    """Ports `make21()`: the 21-step reference strip."""
    for j in range(21):
        value = geo.value_21(j)
        b = layout.patch_bounds_21(j)
        gray_patch(image, layer, b, value)
        if options.numbers:
            text_value = 255.0 if value < 128 else 0.0
            write_text(image, layout.x21 + 6, b.bottom + 20, str(j + 1), text_value, Gimp.TextJustification.LEFT)
            layer = image.flatten()
    _deselect(image)
    return layer


def build_chart(label: str, layout: ChartLayout, options: Optional[ChartOptions] = None) -> Gimp.Image:
    """Ports `buildChart()`. Returns the finished `Gimp.Image`; saving/
    displaying/naming it is a Phase 4 (UI/plugin) concern, not this
    module's -- `gChartName` (the original's *document* name) has no
    equivalent here yet for that reason."""
    if options is None:
        options = ChartOptions()

    width = int(round(layout.width))
    height = int(round(layout.height))
    image = Gimp.Image.new(width, height, Gimp.ImageBaseType.RGB)
    image.set_resolution(layout.dpi, layout.dpi)

    bg_layer = Gimp.Layer.new(
        image, "Background", width, height, Gimp.ImageType.RGB_IMAGE, 100.0, Gimp.LayerMode.NORMAL
    )
    image.insert_layer(bg_layer, None, 0)
    Gimp.context_set_foreground(_gray_color(255.0))
    bg_layer.edit_fill(Gimp.FillType.FOREGROUND)
    layer = image.flatten()

    layer = make101(image, layer, layout, options)
    layer = make21(image, layer, layout, options)

    c_ctr = layout.x_marg + layout.patch * 5.5
    c_bot = layout.y_marg + layout.patch * 11
    center = Gimp.TextJustification.CENTER

    write_text(
        image, c_ctr, c_bot - layout.dpi_scale * 75, f"{CHART_TITLE} ©2006-2019 Kevin Bjorke",
        0.0, center, CREDIT_POINT_SIZE,
    )
    write_text(image, c_ctr, c_bot - layout.dpi_scale * 58, "http://www.botzilla.com/", 0.0, center, CREDIT_POINT_SIZE)
    write_text(
        image, c_ctr, c_bot - layout.dpi_scale * 41, "Original Chart Design by Thomas Howard",
        0.0, center, CREDIT_POINT_SIZE,
    )
    write_text(image, c_ctr, c_bot - layout.dpi_scale * 24, "http://LuminaryArts.com/", 0.0, center, CREDIT_POINT_SIZE)
    # These two lines keep the *default* LABEL_POINT_SIZE, unlike the four
    # above -- matches the original, which never overrides .textItem.size
    # for them (see module docstring / API_MAPPING.md).
    write_text(image, c_ctr, c_bot - layout.dpi_scale * 3, "THIS IS A POSITIVE IMAGE WITH DARK TEXT ON WHITE", 0.0, center)
    write_text(image, c_ctr, c_bot + layout.dpi_scale * 17, "MORE INFO: https://github.com/joker-b/ChartThrob", 0.0, center)
    layer = image.flatten()

    vertical_grad(image, layer, layout)
    layer = image.flatten()

    draw_bars(image, layer, layout, layout.x_bar, 10.0)
    out_stroke(image, layer, layout)

    write_text(
        image, layout.x_marg + layout.patch * 5, layout.y_marg - layout.dpi_scale * 20, label,
        0.0, center, BIG_LABEL_POINT_SIZE,
    )
    layer = image.flatten()

    return image
