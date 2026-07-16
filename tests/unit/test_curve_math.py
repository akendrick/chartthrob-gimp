"""Unit tests for chartthrob.curve_math.

Covers: gray conversion, paper-tone normalization (including the dark-paper
warning and the zero-paper-channel edge case), dynamic-range computation
(including tie-breaking and the degenerate/linear-ramp fallback), the
inverse-interpolation curve lookup (including its documented boundary
returns), and the monotonicity/negation helpers -- including a pinned
regression test for the original's "only compares against the first point"
quirk in verifyCurve.
"""
from __future__ import annotations

import math

import pytest

from chartthrob import curve_math as cm


# --- to_gray -----------------------------------------------------------


def test_to_gray_is_flat_average():
    assert cm.to_gray(cm.RGB(0, 0, 0)) == 0.0
    assert cm.to_gray(cm.RGB(255, 255, 255)) == 255.0
    assert cm.to_gray(cm.RGB(255, 0, 0)) == pytest.approx(85.0)


# --- normalize_paper_tone ------------------------------------------------


def test_normalize_paper_tone_normal_case():
    samples = [cm.RGB(200, 200, 200), cm.RGB(100, 100, 100), cm.RGB(0, 0, 0)]
    result = cm.normalize_paper_tone(samples)
    assert result.dark_paper_warning is False
    assert result.gray_values[0] == pytest.approx(255.0)  # paper tone maps to itself -> 255
    assert result.gray_values[1] == pytest.approx(127.5)
    assert result.gray_values[2] == pytest.approx(0.0)


def test_normalize_paper_tone_dark_paper_warning():
    samples = [cm.RGB(100, 100, 100), cm.RGB(50, 50, 50)]
    result = cm.normalize_paper_tone(samples)
    assert result.dark_paper_warning is True


def test_normalize_paper_tone_clamps_above_255():
    # A sample brighter than the "paper" reference (e.g. specular highlight)
    # must clamp to 255, not exceed it.
    samples = [cm.RGB(100, 100, 100), cm.RGB(150, 150, 150)]
    result = cm.normalize_paper_tone(samples)
    assert result.gray_values[1] == 255.0


def test_normalize_paper_tone_zero_paper_channel_nonzero_sample_clamps_to_255():
    # paper.red == 0, but this sample's red channel is nonzero -> JS
    # Infinity -> clamped to 255.
    samples = [cm.RGB(0, 100, 100), cm.RGB(30, 50, 50)]
    result = cm.normalize_paper_tone(samples)
    assert result.gray_values[1] == pytest.approx((255.0 + 127.5 + 127.5) / 3.0)


def test_normalize_paper_tone_zero_paper_and_zero_sample_channel_yields_nan():
    # paper.red == 0 AND this sample's red channel is ALSO 0 -> JS 0/0 ->
    # NaN, and `NaN > 255` is false so the clamp never fires. This is the
    # paper-tone patch normalized against itself, so it hits this exact case.
    samples = [cm.RGB(0, 100, 100)]
    result = cm.normalize_paper_tone(samples)
    assert math.isnan(result.gray_values[0])


def test_normalize_paper_tone_requires_at_least_one_sample():
    with pytest.raises(ValueError):
        cm.normalize_paper_tone([])


# --- compute_dynamic_range ------------------------------------------------


def test_compute_dynamic_range_normal_spread():
    values = [0.0, 50.0, 100.0]
    dr = cm.compute_dynamic_range(values)
    assert dr.degenerate is False
    assert dr.min_value == 0.0
    assert dr.max_value == 100.0
    assert dr.normalized == [0.0, 128.0, 255.0]


def test_compute_dynamic_range_degenerate_all_equal_falls_back_to_linear_ramp():
    values = [42.0] * 5
    dr = cm.compute_dynamic_range(values)
    assert dr.degenerate is True
    assert dr.normalized == [0.0, 64.0, 128.0, 191.0, 255.0]


def test_compute_dynamic_range_single_value_degenerate_case():
    dr = cm.compute_dynamic_range([10.0])
    assert dr.degenerate is True
    assert dr.normalized == [255.0]


def test_compute_dynamic_range_min_index_tie_break_takes_last_match():
    values = [5.0, 5.0, 5.0, 50.0]
    dr = cm.compute_dynamic_range(values)
    assert dr.min_index == 2  # last index tied at the minimum, not the first


def test_compute_dynamic_range_max_index_tie_break_takes_last_match():
    values = [5.0, 50.0, 50.0, 50.0]
    dr = cm.compute_dynamic_range(values)
    assert dr.max_index == 3  # last index tied at the maximum, not the first


def test_compute_dynamic_range_requires_at_least_one_value():
    with pytest.raises(ValueError):
        cm.compute_dynamic_range([])


# --- find_value_for --------------------------------------------------------


@pytest.fixture
def descending_samples():
    # A clean linear descending sample set: index 0 -> 255 (lightest),
    # index 10 -> 0 (darkest), matching the original's expected patch order.
    return [255.0 - 25.5 * i for i in range(11)]


def test_find_value_for_exact_match(descending_samples):
    # samples[4] == 255 - 25.5*4 == 153.0, exactly on a sample.
    result = cm.find_value_for(153.0, descending_samples)
    assert result == pytest.approx(255.0 * (1.0 - 4 / 10.0))


def test_find_value_for_interpolates_between_neighbors(descending_samples):
    # Halfway between samples[4]=153.0 and samples[3]=178.5 -> orig 165.75
    result = cm.find_value_for(165.75, descending_samples)
    expected_n = 4 - 0.5
    assert result == pytest.approx(255.0 * (1.0 - expected_n / 10.0))


def test_find_value_for_zero_boundary(descending_samples):
    result = cm.find_value_for(0.0, descending_samples)
    assert result is not None
    assert 0.0 <= result <= 255.0


def test_find_value_for_zero_boundary_falls_back_to_last_sample_when_all_zero():
    # No sample is ever > 0, so the reverse scan never breaks; the fallback
    # sets i = L-1 and reads the last sample directly.
    samples = [0.0, 0.0, 0.0]
    result = cm.find_value_for(0.0, samples)
    assert result == pytest.approx(0.0)


def test_find_value_for_highest_boundary(descending_samples):
    result = cm.find_value_for(255.0, descending_samples)
    assert result == pytest.approx(255.0)


def test_find_value_for_plateau_samples_does_not_crash():
    # Two adjacent equal samples (a tie from compute_dynamic_range) must
    # not raise, and must still return a value in range.
    samples = [255.0, 200.0, 200.0, 0.0]
    result = cm.find_value_for(150.0, samples)
    assert result is not None
    assert 0.0 <= result <= 255.0


def test_find_value_for_unreachable_high_value_returns_none():
    # All samples already below orig_value -> "sample values start above" path.
    samples = [100.0, 90.0, 80.0]
    assert cm.find_value_for(250.0, samples) is None


def test_find_value_for_unreachable_low_value_returns_none():
    # orig_value below every sample and i lands at 0 on a non-equal match.
    samples = [100.0, 90.0, 80.0]
    assert cm.find_value_for(5.0, samples) is None


def test_find_value_for_too_few_samples_returns_none():
    assert cm.find_value_for(100.0, [200.0]) is None
    assert cm.find_value_for(100.0, []) is None


def test_find_value_for_extrapolates_outside_0_255_for_narrow_range_samples():
    """Pinned regression test: find_value_for never clamps its output. If
    fed samples that don't span the full 0..255 range (which never happens
    in the real pipeline, where samples always come from
    compute_dynamic_range -- see that function's docstring), it will
    linearly extrapolate past the [0, 255] curve range, exactly like the
    original's unclamped `255 * (1 - n/(L-1))`.
    """
    result = cm.find_value_for(0.0, [2.0, 1.0])
    assert result == pytest.approx(-255.0)


# --- verify_curve / negate_curve -------------------------------------------


def test_verify_curve_accepts_strictly_increasing_points():
    points = [(0.0, 0.0), (50.0, 60.0), (100.0, 120.0)]
    assert cm.verify_curve(points) is True


def test_verify_curve_rejects_point_below_first_x():
    points = [(50.0, 60.0), (10.0, 5.0)]
    assert cm.verify_curve(points) is False


def test_verify_curve_empty_is_trivially_valid():
    assert cm.verify_curve([]) is True


def test_verify_curve_quirk_dip_above_first_point_still_passes():
    """Pinned regression test for the ORIGINAL's actual behavior: it never
    updates its comparison baseline inside the loop, so a curve that rises
    then dips -- as long as it never dips below the very FIRST point's
    x-value -- is accepted, even though it isn't pairwise monotonic.
    """
    # x goes 10 -> 100 -> 50: not pairwise monotonic (100 -> 50 dips), but
    # 50 is still >= the first point's x (10), so the original -- and this
    # port -- both accept it.
    points = [(10.0, 0.0), (100.0, 90.0), (50.0, 40.0)]
    assert cm.verify_curve(points) is True


def test_verify_curve_quirk_dip_below_first_point_fails():
    points = [(10.0, 0.0), (100.0, 90.0), (5.0, 2.0)]
    assert cm.verify_curve(points) is False


def test_negate_curve_applies_255_minus_y():
    points = [(0.0, 10.0), (128.0, 128.0), (255.0, 250.0)]
    negated = cm.negate_curve(points)
    assert negated == [(0.0, 245.0), (128.0, 127.0), (255.0, 5.0)]
    # x values are untouched by negation
    assert [p[0] for p in negated] == [p[0] for p in points]


def test_negate_curve_is_an_involution():
    points = [(0.0, 10.0), (128.0, 128.0), (255.0, 250.0)]
    assert cm.negate_curve(cm.negate_curve(points)) == points
