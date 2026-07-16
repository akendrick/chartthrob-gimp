"""The 11-case stress-test table from docs/PLAN.md section 2.6, made
concrete and individually named so a reviewer can check the plan's table
directly against test names here, rather than hunting for scattered
coverage across tests/unit/.

IMPORTANT: a few of these cases' *expected behavior* was corrected from
PLAN.md's original planning-time guess, based on what real execution
against curve_math.py actually does -- each such correction is called out
explicitly in that test's docstring. That's the same "verify, don't
assume" standard the rest of this project holds GIMP-facing code to,
applied here to the plan document itself.

Cases #6 (non-RGB image mode) and #11 (full build->distort->analyze
round-trip) need a running GIMP and can't be expressed as plain pytest
cases -- they're marked `skip` here (so this table stays a complete,
one-to-one index of all 11 cases) pointing at their real GIMP-backed
implementations in tests/integration/.
"""
from __future__ import annotations

import pytest

from chartthrob import curve_math as cm
from chartthrob import geometry as geo


# --- Case 1 ------------------------------------------------------------


def test_case_01_all_patches_identical_raises_rather_than_gracefully_degrades():
    """PLAN.md table: 'All 101 patches identical value -> Degenerate
    dynamic range -> linear-ramp fallback, no crash.'

    CORRECTED: `compute_dynamic_range` does hit its degenerate/linear-ramp
    fallback with no crash (see tests/unit/test_curve_math.py), but that
    fallback's ramp runs the *opposite* direction from what
    `find_value_for` expects (documented in `compute_dynamic_range`'s own
    docstring and PLAN.md section 3.2 item 3). The practical, verified
    consequence -- confirmed here, not assumed -- is that a genuinely
    all-identical scan raises `CurveBuildError` (the "not enough valid
    points" guard), not a silently-produced pseudo-linear curve.
    """
    samples = [cm.RGB(150.0, 150.0, 150.0)] * 101
    with pytest.raises(cm.CurveBuildError, match="[Nn]ot enough"):
        cm.build_curve_from_samples(samples)


# --- Case 2 ------------------------------------------------------------


def test_case_02_dark_but_legitimate_paper_tone_warns_but_still_succeeds():
    """PLAN.md table: 'Inverted scan (paper tone below threshold) ->
    "possibly scanned a negative" warning flag returned.'

    This is the case where the paper-tone patch simply reads dark for a
    legitimate reason (toned paper, a process with an inherent color
    cast) while the rest of the chart still ramps correctly from light to
    dark. Confirmed: `dark_paper_warning` is set, and the curve still
    comes out with the full 14 points -- the warning does not, by itself,
    indicate a failure. (`tests/golden/fixtures/dark_paper_tone_scan.json`
    is this exact scenario, kept there as the pinned golden vector; this
    test exists as the stress-table's own direct entry point.)
    """
    samples = [cm.RGB(100.0 - i * 0.95, 100.0 - i * 0.95, 100.0 - i * 0.95) for i in range(101)]
    result = cm.build_curve_from_samples(samples)
    assert result.dark_paper_warning is True
    assert len(result.curve_points) == 14


def test_case_02b_genuinely_reversed_scan_raises_rather_than_a_nonsense_curve():
    """Bonus case beyond PLAN.md's original table, added because testing
    case 2 surfaced it: a scan that's *actually* reversed (e.g. the FAQ's
    "accidentally scanned a negative image" scenario, where patch 0 reads
    darkest and patch 100 reads lightest -- not just a dark paper tone)
    is a fundamentally different situation from case 2 above, even though
    both can trip `dark_paper_warning`. Confirmed: this correctly raises
    `CurveBuildError` rather than silently producing a backwards curve --
    arguably the *right* outcome, even though the original's error message
    for this path is the generic "not enough samples" alert rather than
    anything specifically diagnosing a reversed scan.
    """
    samples = [cm.RGB(20.0 + i * 2.1, 20.0 + i * 2.1, 20.0 + i * 2.1) for i in range(101)]
    with pytest.raises(cm.CurveBuildError):
        cm.build_curve_from_samples(samples)


# --- Case 3 ------------------------------------------------------------


def test_case_03_small_scan_dimensions_still_produce_well_formed_sample_bounds():
    """PLAN.md table: 'Extremely small crop (sample area smaller than
    patch grid) -> Clear error, or documented degraded-but-monotonic
    output -- not silent garbage.'

    CLARIFIED: neither this port nor the original has an explicit
    "too-small crop" error path -- the original's FAQ just advises against
    scans smaller than ~600px without enforcing it in code, and this port
    preserves that (no invented guard where the original had none, see
    docs/API_MAPPING.md). What's actually verifiable is that
    `geometry.patch_sample_bounds`'s formulas stay well-formed (positive
    width/height, centered, ordered `left<right`/`bottom<top`) down to
    very small scan dimensions, i.e. it degrades numerically rather than
    producing nonsense -- "silent garbage" specifically ruled out, "clear
    error" specifically not claimed.
    """
    for size in (50, 20, 11):
        for i in range(10):
            for j in range(11):
                b = geo.patch_sample_bounds(size, size, i, j)
                assert b.left < b.right
                assert b.bottom < b.top
                assert 0 <= b.left and b.right <= size
                assert 0 <= b.bottom and b.top <= size


# --- Case 4 --------------------------------------------------------------


def test_case_04_dpi_below_72_clamps_to_72():
    """PLAN.md table: 'DPI below 72 -> Clamped to 72, matching original.'
    Direct stress-table entry point; full coverage of clamp_dpi's edge
    values lives in tests/unit/test_geometry.py."""
    assert geo.clamp_dpi(10.0) == 72.0
    assert geo.ChartLayout.from_dpi(1.0).dpi == 72.0


# --- Case 5 --------------------------------------------------------------


def test_case_05_dpi_absurdly_high_does_not_overflow():
    """PLAN.md table: 'DPI absurdly high (e.g. 4800) -> Layout math
    doesn't overflow; rounds sanely.'"""
    layout = geo.ChartLayout.from_dpi(4800.0)
    assert layout.dpi == 4800.0
    assert layout.width == pytest.approx(1200.0 * (4800.0 / 300.0))
    assert layout.height == pytest.approx(1210.0 * (4800.0 / 300.0))
    # every patch bound should still be finite and well-ordered
    for i in range(10):
        b = layout.patch_bounds_101(i, 5)
        assert b.left < b.right
        assert b.bottom < b.top


# --- Case 6 (needs real GIMP) --------------------------------------------


@pytest.mark.skip(
    reason=(
        "Needs a running GIMP (Gimp.Image.get_base_type/convert_rgb). "
        "See tests/integration/manual_ensure_rgb.py, run via "
        "scripts/run_gimp_batch.sh."
    )
)
def test_case_06_non_rgb_image_attempts_conversion_then_errors_cleanly():
    """PLAN.md table: 'Non-RGB image fed to analyzer (grayscale/CMYK/
    indexed/bitmap) -> Attempts conversion; on failure, clean error, no
    partial state left behind.'"""


# --- Case 7 ------------------------------------------------------------


def test_case_07_negate_plus_degenerate_raises_before_negation_ever_runs():
    """PLAN.md table: 'Negate toggle + degenerate/linear-fallback curve ->
    Still valid, monotonic-after-negation output.'

    CORRECTED: since case 1 (above) establishes that a genuinely
    degenerate scan raises `CurveBuildError` before ever reaching the
    curve-points list, `negate=True` can't change that outcome --
    `negate_curve()` is only ever applied to an already-verified,
    already-non-empty curve. Confirmed here directly: identical exception,
    identical message, whether or not `negate` is set.
    """
    samples = [cm.RGB(150.0, 150.0, 150.0)] * 101
    with pytest.raises(cm.CurveBuildError, match="[Nn]ot enough"):
        cm.build_curve_from_samples(samples, negate=True)


# --- Case 8 ------------------------------------------------------------


def test_case_08_orig_value_boundaries_0_and_255():
    """PLAN.md table: 'orig_value exactly 0 and exactly 255 -> Correct
    boundary handling, no off-by-one.'

    Exercised here through the full `build_curve_from_samples` pipeline
    (a clean scan's first/last curve points are exactly the 0/255
    endpoints); the exhaustive boundary-condition unit tests for
    `find_value_for` itself live in tests/unit/test_curve_math.py.
    """
    samples = [cm.RGB(250.0 - i * 2.42, 250.0 - i * 2.42, 250.0 - i * 2.42) for i in range(101)]
    result = cm.build_curve_from_samples(samples)
    assert result.curve_points[0][0] == 0.0
    assert result.curve_points[0][1] == pytest.approx(0.0, abs=1.0)
    assert result.curve_points[-1][0] == 255.0
    assert result.curve_points[-1][1] == pytest.approx(255.0, abs=1.0)


# --- Case 9 ------------------------------------------------------------


def test_case_09_fewer_than_two_valid_points_raises():
    """PLAN.md table: 'Fewer than 2 valid curve points -> Aborts with "not
    enough samples," matching original's `i < 2` guard.'

    Reuses case 1's degenerate scenario as the concrete trigger (it's the
    most direct, realistic way to drive the valid-point count below 2);
    what's being asserted here specifically is the guard's own threshold
    (`len(curve_points) < 2`), not the degenerate-fallback mechanism
    itself (that's case 1's concern).
    """
    samples = [cm.RGB(150.0, 150.0, 150.0)] * 101
    with pytest.raises(cm.CurveBuildError, match="[Nn]ot enough"):
        cm.build_curve_from_samples(samples)


# --- Case 10 -----------------------------------------------------------


def test_case_10_non_monotonic_curve_points_are_unreachable_via_the_real_pipeline():
    """PLAN.md table: 'Non-progressive (non-monotonic) curve points, e.g.
    from a mis-cropped chart -> Caught by verify_curve, never written into
    an output curve.'

    CLARIFIED, not merely corrected: `build_curve_from_samples` builds its
    curve-point x-values as `round_half_up(255*j/13)` for `j` in a fixed
    `range(14)` and only ever *filters* that already strictly-increasing
    sequence (never reorders or perturbs it) -- so the x-values
    `verify_curve` checks can provably never be non-monotonic when they
    come from this real pipeline, regardless of how corrupted the input
    samples are. `verify_curve`'s monotonicity guard is only reachable
    with hand-constructed points that bypass this pipeline entirely --
    which is exactly what tests/unit/test_curve_math.py's
    `test_verify_curve_quirk_*` tests already do directly. This test pins
    the *pipeline-level* claim (not reachable here) rather than
    re-deriving what's already covered there.
    """
    samples = [cm.RGB(250.0 - i * 2.42, 250.0 - i * 2.42, 250.0 - i * 2.42) for i in range(101)]
    result = cm.build_curve_from_samples(samples)
    xs = [x for x, _y in result.curve_points]
    assert xs == sorted(xs)
    assert len(xs) == len(set(xs))  # strictly increasing, not just non-decreasing


# --- Case 11 (needs real GIMP) -------------------------------------------


@pytest.mark.skip(
    reason=(
        "Needs a running GIMP (build a chart, apply a known distortion, "
        "analyze it). See tests/integration/manual_full_roundtrip.py, run "
        "via scripts/run_gimp_batch.sh -- this is PLAN.md's SC1 proof."
    )
)
def test_case_11_full_roundtrip_recovers_a_known_distortion():
    """PLAN.md table: 'Full round-trip: build -> apply known monotonic
    distortion -> analyze -> Recovered curve approximately cancels the
    distortion within tolerance -- this is SC1.'"""
