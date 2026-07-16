"""Golden-vector tests: pin curve_math.build_curve_from_samples()'s exact
output for documented, formula-defined realistic scenarios.

These are regression pins, not independent correctness proofs -- the math
itself is proven correct by tests/unit/ and tests/property/. What this
suite proves is that a reviewing AI (or human) can inspect
tests/golden/fixtures/*.json directly, see the exact input formula (in each
fixture's "description") and exact expected output, and trust that this
port's behavior for these scenarios is pinned: any future change that
alters it will fail here and must be a deliberate, reviewed decision (see
tests/golden/generate_fixtures.py's module docstring for how to regenerate
after such a change).
"""
from __future__ import annotations

import json
import os

import pytest

from chartthrob import curve_math as cm

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

FIXTURE_NAMES = [
    "clean_linear_scan",
    "low_contrast_scan",
    "dark_paper_tone_scan",
    "clipped_patch_scan",
    "clean_linear_scan_negated",
]


def _load_fixture(name: str) -> dict:
    with open(os.path.join(FIXTURES_DIR, f"{name}.json")) as f:
        return json.load(f)


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_golden_vector(name):
    fixture = _load_fixture(name)
    samples = [cm.RGB(*s) for s in fixture["samples"]]
    negate = fixture["negate"]
    expected = fixture["expected"]

    result = cm.build_curve_from_samples(samples, negate=negate)

    assert len(result.curve_points) == len(expected["curve_points"])
    for (x, y), (ex, ey) in zip(result.curve_points, expected["curve_points"]):
        assert x == pytest.approx(ex)
        assert y == pytest.approx(ey)

    dr = expected["dynamic_range"]
    assert result.dynamic_range.min_value == pytest.approx(dr["min_value"])
    assert result.dynamic_range.max_value == pytest.approx(dr["max_value"])
    assert result.dynamic_range.min_index == dr["min_index"]
    assert result.dynamic_range.max_index == dr["max_index"]
    assert result.dynamic_range.degenerate == dr["degenerate"]

    assert list(result.paper_color) == pytest.approx(expected["paper_color"])
    assert result.dark_paper_warning == expected["dark_paper_warning"]
    assert result.negated == expected["negated"]
    assert result.curve_name == expected["curve_name"]


def test_dark_paper_tone_scan_actually_triggers_the_warning():
    # A fixture-specific sanity check beyond the generic loop above: this
    # scenario exists specifically to exercise dark_paper_warning, so
    # assert that directly rather than trusting the recorded expectation
    # alone -- if the fixture were ever regenerated against a broken
    # normalize_paper_tone that stopped setting the flag, this still fails.
    fixture = _load_fixture("dark_paper_tone_scan")
    samples = [cm.RGB(*s) for s in fixture["samples"]]
    result = cm.build_curve_from_samples(samples)
    assert result.dark_paper_warning is True


def test_clipped_patch_scan_x_zero_drops_out_of_the_curve():
    # Pins the specific, non-obvious finding described in this fixture:
    # the clipped patch corrupts compute_dynamic_range's recorded minimum
    # enough that x=0.0 has no valid bracketing sample and is excluded
    # from the curve entirely -- not an error, just a silently shorter
    # curve. See generate_fixtures.py's description for the full mechanism.
    fixture = _load_fixture("clipped_patch_scan")
    samples = [cm.RGB(*s) for s in fixture["samples"]]
    result = cm.build_curve_from_samples(samples)
    xs = [x for x, _y in result.curve_points]
    assert 0.0 not in xs
    assert len(result.curve_points) == 13  # one short of the usual 14


def test_negation_is_consistent_with_the_non_negated_fixture():
    # clean_linear_scan_negated should be exactly clean_linear_scan's curve
    # with negate_curve() applied -- cross-checks the two fixtures against
    # each other, not just each against its own recorded expectation.
    plain = _load_fixture("clean_linear_scan")
    negated = _load_fixture("clean_linear_scan_negated")
    expected_negated_points = cm.negate_curve(
        [tuple(p) for p in plain["expected"]["curve_points"]]
    )
    for (x, y), (ex, ey) in zip(negated["expected"]["curve_points"], expected_negated_points):
        assert x == pytest.approx(ex)
        assert y == pytest.approx(ey)
