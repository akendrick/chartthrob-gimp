"""Manual smoke check: build a real chart inside a real GIMP process.

NOT collected by pytest (pytest has no `Gimp` module available, and this
file is intentionally named so pytest's `test_*.py` discovery skips it).
Run it directly against a real GIMP 3 install instead:

    scripts/run_gimp_batch.sh tests/integration/manual_build_chart_smoke.py

This is Phase 2's "does it actually run in GIMP" check (PLAN.md SC5, partial
-- SC5 in full also covers Phase 4's plugin registration). The full
automated headless round-trip proof (build -> distort -> analyze, SC1) is
Phase 3/5 scope and belongs in tests/integration/test_full_roundtrip.py
once chart_analyzer.py exists.
"""
import sys

sys.path.insert(0, "/Users/kendrick/Documents/CODE/ChartThrob-GIMP")

from chartthrob import chart_builder as cb
from chartthrob import geometry as geo

DPI = 72.0  # small on purpose -- this only checks that real GIMP calls
# succeed and produce sane structure, not visual fidelity, so a small,
# fast-to-build chart is enough.

layout = geo.ChartLayout.from_dpi(DPI)
options = cb.ChartOptions(numbers=True, outlines=True)

image = cb.build_chart("Smoke Test", layout, options)

expected_width = round(layout.width)
expected_height = round(layout.height)
actual_width = image.get_width()
actual_height = image.get_height()
num_layers = len(image.get_layers())

assert actual_width == expected_width, f"width {actual_width} != expected {expected_width}"
assert actual_height == expected_height, f"height {actual_height} != expected {expected_height}"
assert num_layers == 1, f"expected a single flattened layer, got {num_layers}"

print(f"OK width={actual_width} height={actual_height} layers={num_layers}")
print("MANUAL_BUILD_CHART_SMOKE_PASSED")

image.delete()
