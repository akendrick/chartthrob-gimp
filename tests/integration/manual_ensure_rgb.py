"""Manual proof for stress-test case 6 (tests/stress/test_stress_cases.py):
non-RGB images fed to the analyzer attempt conversion, and succeed.

NOT collected by pytest (no `Gimp` module there; filename intentionally
doesn't match `test_*.py`). Run directly:

    scripts/run_gimp_batch.sh tests/integration/manual_ensure_rgb.py

Covers the two mode-conversion paths `chart_analyzer.ensure_rgb()` actually
guards (GIMP's core `ImageBaseType` only has RGB/GRAY/INDEXED -- see that
function's docstring for why the original's BITMAP/CMYK/DUOTONE checks
have nothing to map to here). The *failure* branch (an actual
`convert_rgb()` failure) is not exercised here: it's a defensive
`try/except` around a GIMP core operation that doesn't practically fail
for a real GRAY/INDEXED image, similar in spirit to `curve_math.py`'s
already-documented `delta == 0` dead branch in `find_value_for` -- kept
for fidelity to the original's own defensive `try/catch`, not because a
failure is reachable here.
"""
import sys

import os
ROOT = os.environ["CHARTTHROB_ROOT"]  # exported by scripts/run_gimp_batch.sh
sys.path.insert(0, ROOT)

from chartthrob import chart_analyzer as ca

for mode_name, base_type in [
    ("GRAY", Gimp.ImageBaseType.GRAY),
    ("INDEXED", Gimp.ImageBaseType.INDEXED),
]:
    image = Gimp.Image.new(8, 8, base_type)
    layer = Gimp.Layer.new(
        image, "p", 8, 8,
        Gimp.ImageType.GRAYA_IMAGE if base_type == Gimp.ImageBaseType.GRAY else Gimp.ImageType.INDEXEDA_IMAGE,
        100.0, Gimp.LayerMode.NORMAL,
    )
    image.insert_layer(layer, None, 0)
    assert image.get_base_type() == base_type

    ca.ensure_rgb(image)

    assert image.get_base_type() == Gimp.ImageBaseType.RGB, f"{mode_name} did not convert to RGB"
    print(f"{mode_name} -> RGB conversion OK")
    image.delete()

# RGB images should be left alone (no-op, no exception).
rgb_image = Gimp.Image.new(8, 8, Gimp.ImageBaseType.RGB)
ca.ensure_rgb(rgb_image)
assert rgb_image.get_base_type() == Gimp.ImageBaseType.RGB
rgb_image.delete()
print("RGB no-op OK")

print("MANUAL_ENSURE_RGB_PASSED")
