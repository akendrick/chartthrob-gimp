"""Generates the golden-vector fixtures in tests/golden/fixtures/*.json.

Not itself a test -- a regenerable tool. Run it directly to (re)create the
fixtures after a *deliberate* behavior change to curve_math.py:

    python3 tests/golden/generate_fixtures.py

Each fixture pins curve_math.build_curve_from_samples()'s exact output for
a documented, formula-defined set of 101 synthetic RGB samples. This is
golden-master testing, not independent verification: correctness of the
underlying math is Phase 1's unit/property tests' job (tests/unit/,
tests/property/). What this proves is that a *reviewing AI or human can
regenerate the same numbers from the same formula* and get an identical
result -- i.e. the port's behavior for these specific, realistic scenarios
is pinned and any future change to it will show up as a diff here that
must be deliberately reviewed and regenerated, not silently absorbed.

If you regenerate a fixture, diff it before committing -- an unexpected
change here means curve_math.py's behavior changed, which should be a
deliberate, reviewed decision (see docs/API_MAPPING.md), never a surprise.
"""
import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from chartthrob import curve_math as cm

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _linear_ramp_samples(paper_tone: float, black_tone: float, clip_index=None, clip_value=None):
    """101 neutral-gray RGB samples: sample[0] is the paper-tone reference
    patch, sample[100] is the darkest patch, and samples[1..99] ramp
    linearly between them -- i.e. a synthetic stand-in for a real chart
    print+scan with no non-linearity at all. `clip_index`/`clip_value`
    optionally corrupt one patch (a dust speck / scanner artifact stand-in).
    """
    samples = []
    for n in range(101):
        gray = paper_tone - (paper_tone - black_tone) * (n / 100.0)
        if clip_index is not None and n == clip_index:
            gray = clip_value
        samples.append((gray, gray, gray))
    return samples


def _build_fixture(name: str, description: str, samples, negate: bool = False):
    result = cm.build_curve_from_samples([cm.RGB(*s) for s in samples], negate=negate)
    fixture = {
        "description": description,
        "samples": [list(s) for s in samples],
        "negate": negate,
        "expected": {
            "curve_points": [list(p) for p in result.curve_points],
            "dynamic_range": {
                "min_value": result.dynamic_range.min_value,
                "max_value": result.dynamic_range.max_value,
                "min_index": result.dynamic_range.min_index,
                "max_index": result.dynamic_range.max_index,
                "degenerate": result.dynamic_range.degenerate,
            },
            "paper_color": list(result.paper_color),
            "dark_paper_warning": result.dark_paper_warning,
            "negated": result.negated,
            "curve_name": result.curve_name,
        },
    }
    path = os.path.join(FIXTURES_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(fixture, f, indent=2)
        f.write("\n")
    print(f"wrote {path}")


def main():
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    _build_fixture(
        "clean_linear_scan",
        "Ideal print+scan: paper reads at 250 (a lightly-toned paper, not "
        "pure white), darkest patch reads at 8, everything between ramps "
        "perfectly linearly -- the best-case input this tool ever sees.",
        _linear_ramp_samples(paper_tone=250.0, black_tone=8.0),
    )

    _build_fixture(
        "low_contrast_scan",
        "A compressed-dynamic-range print: paper only reaches 200, the "
        "darkest patch only reaches 140 -- a real but poorly-exposed "
        "process (still non-degenerate: span is 60, comfortably over the "
        "compute_dynamic_range degenerate threshold of 1).",
        _linear_ramp_samples(paper_tone=200.0, black_tone=140.0),
    )

    _build_fixture(
        "dark_paper_tone_scan",
        "Paper-tone reference patch reads at 100 (below the 128 "
        "dark_paper_warning threshold) -- e.g. a strongly-toned paper or a "
        "cyanotype's blue cast confusing a naive grayscale conversion, per "
        "the original README's own FAQ warning about this.",
        _linear_ramp_samples(paper_tone=100.0, black_tone=5.0),
    )

    _build_fixture(
        "clipped_patch_scan",
        "An otherwise-clean linear scan with one dust-speck/artifact patch: "
        "patch 50 (which should read ~127 on the ramp) is corrupted to a "
        "clipped 0. FINDING, not a bug in this port -- a faithfully-"
        "preserved fragility in the original algorithm, made concrete by "
        "this fixture: the clipped patch becomes the new recorded "
        "compute_dynamic_range minimum (0, at index 50), which breaks the "
        "monotonic-descending-samples assumption find_value_for relies on. "
        "The pipeline does NOT error (verify_curve only checks x-values, "
        "which are untouched) -- it silently returns a curve where x=0.0 "
        "drops out entirely and the y-values for roughly the first half of "
        "the range (x=20..118) collapse to a narrow, substantively wrong "
        "band clustered around 128, instead of tracking x as the clean scan "
        "does. This fixture exists specifically to pin that distorted-but-"
        "not-erroring behavior, not to claim the algorithm handles a single "
        "bad patch gracefully.",
        _linear_ramp_samples(paper_tone=250.0, black_tone=8.0, clip_index=50, clip_value=0.0),
    )

    _build_fixture(
        "clean_linear_scan_negated",
        "Same as clean_linear_scan, but with the negate option on (e.g. "
        "for QuadToneRIP), confirming negation composes correctly with a "
        "realistic full pipeline run, not just in isolation (see "
        "tests/unit/test_curve_math.py's negate_curve unit tests for the "
        "isolated version).",
        _linear_ramp_samples(paper_tone=250.0, black_tone=8.0),
        negate=True,
    )


if __name__ == "__main__":
    main()
