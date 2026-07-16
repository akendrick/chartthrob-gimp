"""Pure tone-correction math for ChartThrob's scan-analysis workflow.

Ported from `toGray`, `grayValues`, `determineDynamicRange`,
`findValueThatGives`, and `verifyCurve` in the original ChartThrob.jsx.
No GIMP calls here -- pixel values come in as plain RGB samples (however
they were read) and curve points go out as plain (x, y) tuples.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, NamedTuple, Optional, Sequence, Tuple

from ._mathutil import round_half_up

CurvePoint = Tuple[float, float]


class RGB(NamedTuple):
    red: float
    green: float
    blue: float


def to_gray(color: RGB) -> float:
    """Ports `toGray(C)`. Deliberately a flat average, not the
    luminance-weighted variant ChartThrob.jsx leaves commented out
    (`red*0.2 + green*0.7 + blue*0.1`) -- preserved as-is for fidelity,
    not an oversight."""
    return (color.red + color.green + color.blue) / 3.0


@dataclass(frozen=True)
class PaperNormalizationResult:
    gray_values: List[float]
    paper_color: RGB
    dark_paper_warning: bool


def _normalize_channel(sample_channel: float, paper_channel: float) -> float:
    """One RGB channel, scaled so the paper-tone sample reads as 255.

    ChartThrob.jsx computes `255 * sample / paper` with no zero-guard. In JS,
    a zero paper channel with a *nonzero* sample gives `Infinity`, which the
    very next line clamps to 255 (`if (nred > 255) nred = 255`) -- but a zero
    paper channel with a sample that is ALSO zero gives `0/0 = NaN`, and
    `NaN > 255` is `false` in JS, so that clamp never fires and `NaN` passes
    through untouched. Both outcomes are reproduced exactly (rather than
    collapsing both to 255, which would misrepresent the original for the
    double-zero case -- itself only reachable from an already-degenerate
    all-black paper-tone reading, which `dark_paper_warning` flags anyway).
    """
    if paper_channel == 0:
        if sample_channel == 0:
            return float("nan")
        return 255.0
    value = 255.0 * sample_channel / paper_channel
    return 255.0 if value > 255.0 else value


def normalize_paper_tone(samples: Sequence[RGB]) -> PaperNormalizationResult:
    """Ports `grayValues(ColorSamples)`. `samples[0]` is always the
    paper-tone reference patch, by the original's convention."""
    if not samples:
        raise ValueError("normalize_paper_tone requires at least one sample")
    paper = samples[0]
    dark_paper_warning = paper.red < 128 or paper.green < 128 or paper.blue < 128
    gray_values: List[float] = []
    for s in samples:
        nred = _normalize_channel(s.red, paper.red)
        ngreen = _normalize_channel(s.green, paper.green)
        nblue = _normalize_channel(s.blue, paper.blue)
        gray_values.append(to_gray(RGB(nred, ngreen, nblue)))
    return PaperNormalizationResult(
        gray_values=gray_values, paper_color=paper, dark_paper_warning=dark_paper_warning
    )


@dataclass(frozen=True)
class DynamicRange:
    normalized: List[float]
    min_value: float
    max_value: float
    min_index: int
    max_index: int
    degenerate: bool


def compute_dynamic_range(values: Sequence[float]) -> DynamicRange:
    """Ports `determineDynamicRange(GraySamples)`.

    Tie-breaking note: the original updates the min/max index on `<=`/`>=`
    comparisons, so on ties the *last* matching index wins, not the first --
    preserved here with an explicit loop rather than `list.index(min(...))`,
    which would silently pick the first tie instead.

    DIRECTION QUIRK, PRESERVED ON PURPOSE: for well-spread input (the normal
    case), `values` is expected in lightest-patch-first order, and the
    output ramps 255 (lightest) down to 0 (darkest) -- the descending order
    `find_value_for` expects. But the *degenerate* fallback below ramps the
    other way, 0 up to 255 by plain index position, regardless of the
    input's actual order. Fed straight into `find_value_for`, that reversed
    ramp does not satisfy its descending-order precondition, so a genuinely
    degenerate (e.g. blank or fully-flat) scan will very likely still fail
    the caller's separate "not enough valid curve points" check immediately
    after this fallback runs, rather than silently producing a usable
    pseudo-linear curve. This is a property of the *original* algorithm,
    reproduced here rather than "fixed," and is flagged for the Phase 3
    scan-analyzer orchestration to handle explicitly (see docs/API_MAPPING.md
    and PLAN.md stress test #1).
    """
    if not values:
        raise ValueError("compute_dynamic_range requires at least one value")
    min_value = float("inf")
    max_value = float("-inf")
    min_index = -1
    max_index = -1
    for i, s in enumerate(values):
        if s <= min_value:
            min_value = s
            min_index = i
        if s >= max_value:
            max_value = s
            max_index = i
    span = max_value - min_value
    n = len(values)
    degenerate = span < 1
    if degenerate:
        # Original fallback: no usable dynamic range, so return a plain
        # linear ramp indexed by position rather than by value.
        if n == 1:
            normalized = [255.0]
        else:
            normalized = [float(round_half_up(255.0 * i / (n - 1.0))) for i in range(n)]
    else:
        normalized = [float(round_half_up(255.0 * (v - min_value) / span)) for v in values]
    return DynamicRange(
        normalized=normalized,
        min_value=min_value,
        max_value=max_value,
        min_index=min_index,
        max_index=max_index,
        degenerate=degenerate,
    )


def find_value_for(orig_value: float, normalized_samples: Sequence[float]) -> Optional[float]:
    """Ports `findValueThatGives(origValue, normalizedSamples)`.

    Contract: `normalized_samples` is expected in the original's patch
    order -- lightest patch first (index 0, value near 255), darkest patch
    last (value near 0), i.e. monotonically non-increasing. Given a desired
    *original* 0-255 image value, this finds where that value falls along
    the patch-index scale (by inverse linear interpolation between the two
    bracketing samples) and converts that fractional index back into an
    output 0-255 curve value via `s = 255 * (1 - n/(L-1))`.

    Returns `None` where the original returned -1 after an `alert()` (no
    bracketing samples found -- e.g. corrupted/miscropped chart data).

    `len(normalized_samples) < 2` also returns `None`: the original never
    guards against this because the real workflow always passes exactly 101
    samples, but a bare 0- or 1-element input would divide by zero in the
    final `n / (L - 1.0)` step (JS produces `Infinity` there instead of
    raising -- this guard exists only so the Python port has a defined,
    crash-free answer for that input, which never occurs in practice).
    """
    L = len(normalized_samples)
    if L < 2:
        return None

    lower_val = -1.0
    i = 0
    if orig_value == 0:
        for i in range(L - 2, -1, -1):
            if orig_value < normalized_samples[i]:
                i = i + 1
                lower_val = normalized_samples[i]
                break
    else:
        for i in range(0, L):
            if orig_value > normalized_samples[i]:
                lower_val = normalized_samples[i]
                break

    if lower_val < 0:
        if orig_value == 0:
            i = L - 1
            lower_val = normalized_samples[i]
        else:
            return None  # sample values start above orig_value

    if orig_value == lower_val:
        n = float(i)
    else:
        if i == 0:
            return None  # sample values never reach orig_value
        higher_val = normalized_samples[i - 1]
        delta = higher_val - lower_val
        if delta == 0:  # pragma: no cover
            # Believed unreachable: reaching this branch requires
            # higher_val == lower_val while orig_value != lower_val, but the
            # loop's own break condition guarantees higher_val >= orig_value
            # > lower_val whenever they differ -- so delta > 0 whenever this
            # branch's guard (orig_value != lower_val) is true. Preserved
            # from the original as a defensive branch anyway, for exact
            # fidelity, rather than removed on the strength of this proof.
            n = float(i)
        else:
            placement = orig_value - lower_val
            t = placement / delta
            n = i - t

    return 255.0 * (1.0 - (n / (L - 1.0)))


def verify_curve(points: Sequence[CurvePoint]) -> bool:
    """Ports `verifyCurve`'s monotonicity check ONLY -- negation was split
    out into `negate_curve` below (see docs/API_MAPPING.md).

    ORIGINAL QUIRK, PRESERVED ON PURPOSE: the original sets its comparison
    baseline once before the loop (`p = curvePoints[0][0]`) and never
    reassigns it, so this only verifies that every later x-value is >= the
    FIRST point's x-value -- it is NOT full pairwise monotonicity against
    each preceding point. A curve that rises then dips (but never dips below
    the first point) passes here, exactly matching the original's actual
    (probably unintended) behavior. See `test_verify_curve_quirk_*` in
    tests/unit/test_curve_math.py for a pinned example.
    """
    if not points:
        return True
    baseline = points[0][0]
    for x, _y in points[1:]:
        if x < baseline:
            return False
    return True


def negate_curve(points: Sequence[CurvePoint]) -> List[CurvePoint]:
    """Ports the negation block from `verifyCurve`
    (`curvePoints[i][1] = 255 - curvePoints[i][1]`), extracted into its own
    function so negation and monotonicity-checking are independently
    testable and callable in either order."""
    return [(x, 255.0 - y) for x, y in points]
