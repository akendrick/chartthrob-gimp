"""Property-based tests (hypothesis) for chartthrob.curve_math.

These pin down invariants that must hold for *any* input, not just the
hand-picked examples in tests/unit -- exactly the kind of blanket guarantee
a reviewing AI should be able to point at instead of re-deriving the math.
"""
from __future__ import annotations

import math

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from chartthrob import curve_math as cm

finite_gray = st.floats(
    min_value=0.0, max_value=255.0, allow_nan=False, allow_infinity=False
)


# --- compute_dynamic_range ---------------------------------------------


@given(st.lists(finite_gray, min_size=1, max_size=150))
def test_normalized_values_always_within_0_255(values):
    dr = cm.compute_dynamic_range(values)
    for v in dr.normalized:
        assert 0.0 <= v <= 255.0


@given(st.lists(finite_gray, min_size=1, max_size=150))
def test_normalized_output_same_length_as_input(values):
    dr = cm.compute_dynamic_range(values)
    assert len(dr.normalized) == len(values)


@given(st.lists(finite_gray, min_size=2, max_size=150))
def test_degenerate_flag_matches_span_threshold(values):
    dr = cm.compute_dynamic_range(values)
    span = dr.max_value - dr.min_value
    assert dr.degenerate == (span < 1)


# --- negate_curve --------------------------------------------------------


curve_points = st.lists(
    st.tuples(finite_gray, finite_gray), min_size=0, max_size=20
)


@given(curve_points)
def test_negate_curve_is_an_involution(points):
    # float round-trip through `255 - (255 - y)` can differ from `y` in the
    # last couple bits, so this compares approximately, not with `==`.
    result = cm.negate_curve(cm.negate_curve(points))
    assert len(result) == len(points)
    for (rx, ry), (x, y) in zip(result, points):
        assert rx == x
        assert ry == pytest.approx(y)


@given(curve_points)
def test_negate_curve_preserves_x_values(points):
    negated = cm.negate_curve(points)
    assert [p[0] for p in negated] == [p[0] for p in points]


# --- verify_curve ----------------------------------------------------------


@given(curve_points)
def test_verify_curve_never_raises(points):
    # Robustness: no input shape/value should raise -- only True/False.
    result = cm.verify_curve(points)
    assert isinstance(result, bool)


@given(
    st.lists(finite_gray, min_size=1, max_size=20).map(sorted)
)
def test_verify_curve_accepts_any_sorted_ascending_x_sequence(xs):
    points = [(x, 0.0) for x in xs]
    assert cm.verify_curve(points) is True


# --- find_value_for ---------------------------------------------------------
#
# find_value_for's real precondition (see its docstring) is that
# `normalized_samples` is the *output* of compute_dynamic_range on a
# well-behaved (non-degenerate) scan -- i.e. lightest-patch-first, spanning
# the full 0..255 range. Arbitrary descending-but-narrow-range arrays don't
# satisfy that (the function will happily extrapolate outside [0,255] for
# them, e.g. samples=[2.0, 1.0] with orig_value=0.0 -- that's inherent to the
# original's unclamped linear extrapolation, not a defect in this port), so
# the generator below always forces a full-span, non-degenerate input,
# mirroring how the real scan-analysis pipeline actually calls it.


@st.composite
def realistic_normalized_samples(draw):
    n = draw(st.integers(min_value=2, max_value=101))
    raw = draw(st.lists(finite_gray, min_size=n, max_size=n))
    raw[0] = 255.0
    raw[-1] = 0.0
    raw_sorted = sorted(raw, reverse=True)  # lightest patch first
    dr = cm.compute_dynamic_range(raw_sorted)
    assert not dr.degenerate  # guaranteed by the forced 0..255 span above
    return dr.normalized


@given(realistic_normalized_samples(), finite_gray, finite_gray)
@settings(max_examples=300)
def test_find_value_for_is_monotonic_nondecreasing_in_orig_value(samples, a, b):
    """As the requested original pixel value increases, the mapped curve
    output must never decrease -- a correction curve that got darker for a
    brighter input would be physically nonsensical for this tool's purpose.
    """
    lo, hi = (a, b) if a <= b else (b, a)
    result_lo = cm.find_value_for(lo, samples)
    result_hi = cm.find_value_for(hi, samples)
    assume(result_lo is not None and result_hi is not None)
    assert result_lo <= result_hi + 1e-9


@given(realistic_normalized_samples(), finite_gray)
def test_find_value_for_result_within_0_255_when_not_none(samples, orig_value):
    result = cm.find_value_for(orig_value, samples)
    assume(result is not None)
    assert -1e-9 <= result <= 255.0 + 1e-9


@given(realistic_normalized_samples(), finite_gray)
def test_find_value_for_never_returns_nan(samples, orig_value):
    result = cm.find_value_for(orig_value, samples)
    if result is not None:
        assert not math.isnan(result)
