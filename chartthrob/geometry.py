"""Pure layout geometry for ChartThrob's calibration chart.

Ported from the global chart-layout constants and the `resetDpi`,
`patchCenter`, `selectPatch`, `make101`, and `make21` functions in the
original ChartThrob.jsx. No GIMP calls here -- this module only computes
coordinates and fill values; drawing them is chart_builder.py's job (Phase 2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from ._mathutil import round_half_up

# Base layout at the reference 300 DPI, taken verbatim from ChartThrob.jsx's
# initial globals (gWidth, gHeight, gXMarg, gYMarg, gPatch, gStripWidth,
# gGradWidth).
_BASE_DPI = 300.0
_BASE_WIDTH = 1200.0
_BASE_HEIGHT = 1210.0
_BASE_X_MARG = 6.0
_BASE_Y_MARG = 75.0
_BASE_PATCH = 100.0
_BASE_STRIP_WIDTH = 85.0
_BASE_GRAD_WIDTH = 50.0

MIN_DPI = 72.0


@dataclass(frozen=True)
class Bounds:
    """A rectangle, matching the original's `boundArray(Left, Right, Bottom,
    Top)` convention."""

    left: float
    right: float
    bottom: float
    top: float

    def to_polygon(self) -> List[Tuple[float, float]]:
        """Corner order matches `boundArray()`: (L,B), (R,B), (R,T), (L,T)."""
        return [
            (self.left, self.bottom),
            (self.right, self.bottom),
            (self.right, self.top),
            (self.left, self.top),
        ]


def clamp_dpi(dpi: float) -> float:
    """Ports the `if (dv<72) dv=72;` floor from `userDialog()` -- charts
    below 72 DPI were never a supported case."""
    return MIN_DPI if dpi < MIN_DPI else dpi


@dataclass(frozen=True)
class ChartLayout:
    """Replaces ChartThrob.jsx's mutable globals (gWidth, gPatch, gX21, ...)
    with an explicit, immutable value computed from a single DPI input."""

    dpi: float
    dpi_scale: float
    width: float
    height: float
    x_marg: float
    y_marg: float
    patch: float
    strip_width: float
    grad_width: float
    x21: float
    x_grad: float
    x_bar: float

    @classmethod
    def from_dpi(cls, dpi: float) -> "ChartLayout":
        """Ports `resetDpi(newDPI)`."""
        dpi = clamp_dpi(dpi)
        scale = dpi / _BASE_DPI
        x_marg = scale * _BASE_X_MARG
        y_marg = scale * _BASE_Y_MARG
        patch = scale * _BASE_PATCH
        strip_width = scale * _BASE_STRIP_WIDTH
        grad_width = scale * _BASE_GRAD_WIDTH
        x21 = x_marg * 2 + 10 * patch
        x_grad = x21 + strip_width
        x_bar = x_grad + grad_width
        return cls(
            dpi=dpi,
            dpi_scale=scale,
            width=scale * _BASE_WIDTH,
            height=scale * _BASE_HEIGHT,
            x_marg=x_marg,
            y_marg=y_marg,
            patch=patch,
            strip_width=strip_width,
            grad_width=grad_width,
            x21=x21,
            x_grad=x_grad,
            x_bar=x_bar,
        )

    def patch_bounds_101(self, i: int, j: int) -> Bounds:
        """Bounds of one cell in the 10-wide grid used by `make101` (j runs
        0..10 inclusive: rows 0-9 are the 10x10 grid, row 10 is the extra
        pure-black patch drawn at i=0)."""
        x = self.x_marg + i * self.patch
        y = self.y_marg + j * self.patch
        return Bounds(left=x, right=x + self.patch, bottom=y, top=y + self.patch)

    def patch_bounds_21(self, j: int) -> Bounds:
        """Bounds of one cell in the 21-step reference strip used by
        `make21`."""
        x2 = self.x21 + self.strip_width
        ht = self.height / 21.0
        y = j * ht
        return Bounds(left=self.x21, right=x2, bottom=y, top=y + ht + 1)


def value_101(n: int) -> int:
    """Fill value (0-255) for patch index n (0..100) in the 10x10+1 grid.
    n=0 is the lightest (white) patch, n=100 is pure black -- the formula
    naturally yields 0 at n=100, matching the original's separately
    hardcoded black patch without needing a special case here."""
    return round_half_up(255 - 255 * (n / 100.0))


def value_21(j: int) -> float:
    """Fill value (0-255) for step j (0..20) of the 21-step reference
    strip."""
    return 255 - 255 * (j / 20.0)


# --- scan-time sampling geometry --------------------------------------------
#
# These border fractions are DPI-independent (the ratios cancel out the DPI
# scale factor), so ChartThrob.jsx computes them once from its initial
# 300-DPI globals and never recomputes them after `resetDpi()`. They're
# applied against whatever pixel size the user's *scanned* image happens to
# be -- not the DPI used when the chart was originally built.

_border_layout = ChartLayout.from_dpi(_BASE_DPI)
BORDER_LEFT = _border_layout.x_marg / _border_layout.width
BORDER_RIGHT = 1.0 - (
    (_border_layout.x_marg + 10 * _border_layout.patch) / _border_layout.width
)
BORDER_TOP = _border_layout.y_marg / _border_layout.height
BORDER_BOTTOM = 1.0 - (
    (_border_layout.y_marg + 11 * _border_layout.patch) / _border_layout.height
)
SAMPLE_FRACTION = 0.55


def patch_center(scan_width: float, scan_height: float, i: int, j: int) -> Tuple[float, float]:
    """Ports `patchCenter(i,j)` -- the pixel center of grid cell (i,j) within
    an arbitrarily-sized *scanned* image (i in 0..9, j in 0..10)."""
    rw = scan_width * (1.0 - (BORDER_RIGHT + BORDER_LEFT))
    rh = scan_height * (1.0 - (BORDER_TOP + BORDER_BOTTOM))
    px = round_half_up(scan_width * BORDER_LEFT + rw * ((i + 0.5) / 10.0))
    py = round_half_up(scan_height * BORDER_TOP + rh * ((j + 0.5) / 11.0))
    return (float(px), float(py))


def patch_sample_bounds(scan_width: float, scan_height: float, i: int, j: int) -> Bounds:
    """Ports `selectPatch(i,j)` -- the (smaller) averaging-sample region
    centered on `patch_center`, sized by `SAMPLE_FRACTION`."""
    cx, cy = patch_center(scan_width, scan_height, i, j)
    rw = scan_width * (1.0 - (BORDER_RIGHT + BORDER_LEFT))
    rh = scan_height * (1.0 - (BORDER_TOP + BORDER_BOTTOM))
    pw = 0.5 * rw * (SAMPLE_FRACTION / 10.0)
    ph = 0.5 * rh * (SAMPLE_FRACTION / 11.0)
    return Bounds(left=cx - pw, right=cx + pw, bottom=cy - ph, top=cy + ph)
