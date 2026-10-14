"""Manual proof for curve-file export (a chartthrob-gimp addition, not in
the original ChartThrob.jsx -- requested by a real user, format
reverse-engineered from a real file that user exported from their own
GIMP 3.2.4 Curves dialog, not guessed from a scraped tutorial).

NOT collected by pytest (no `Gimp` module there; filename intentionally
doesn't match `test_*.py`). Run directly:

    scripts/run_gimp_batch.sh tests/integration/manual_curve_export.py

Covers: `chart_analyzer.export_curve_file()` directly, and the full
Analyze Scan plugin workflow with the optional `curve-file` argument set.
Also checks the output is structurally well-formed (balanced parens,
correct field sequence) against what a real GIMP-exported `.curves` file
looks like -- see docs/API_MAPPING.md for the full field-by-field mapping.

NOT covered here (can't be, without GUI automation): whether GIMP's own
Curves dialog actually re-imports a file this plugin wrote. That was
verified once, manually, by the user who requested this feature.
"""
import importlib.util
import os
import re
import sys

import os
ROOT = os.environ["CHARTTHROB_ROOT"]  # exported by scripts/run_gimp_batch.sh
sys.path.insert(0, ROOT)
sys.path.insert(0, ROOT + "/plugin/chartthrob-plugin")

from chartthrob import chart_analyzer as ca

_TMP_DIR = "/tmp/chartthrob_manual_curve_export_test"
os.makedirs(_TMP_DIR, exist_ok=True)


def _field_sequence(path):
    with open(path) as f:
        text = f.read()
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            assert depth >= 0, f"unbalanced parens in {path}"
    assert depth == 0, f"unbalanced parens in {path} (ended at depth {depth})"
    return re.findall(r"\(([a-zA-Z][a-zA-Z0-9_-]*)", text)


EXPECTED_FIELD_SEQUENCE = (
    ["time", "trc"]
    + ["channel", "curve", "curve-type", "points", "point-types", "n-samples", "samples"] * 5
)

# --- export_curve_file() directly -------------------------------------------

points = [
    (0.0, 0.0), (20.0, 24.0), (39.0, 45.0), (59.0, 63.0), (78.0, 80.0),
    (98.0, 98.0), (118.0, 118.0), (137.0, 137.0), (157.0, 156.0), (177.0, 174.0),
    (196.0, 193.0), (216.0, 213.0), (235.0, 233.0), (255.0, 255.0),
]
direct_path = os.path.join(_TMP_DIR, "direct_export.curves")
ca.export_curve_file(points, direct_path)
assert os.path.exists(direct_path)
assert _field_sequence(direct_path) == EXPECTED_FIELD_SEQUENCE
with open(direct_path) as f:
    content = f.read()
assert content.startswith("# GIMP 'Curves' settings")
assert "(trc perceptual)" in content
# endpoints must be bare integers, not "0.0"/"1.0" -- confirmed against a
# real GIMP-exported file that this is how GIMP itself formats them.
assert "(points 28 0 0 " in content
assert " 1 1)\n" in content
print("DIRECT_EXPORT_OK")

# --- Through the real plugin's analyze_scan_run(), via a real chart -------

from chartthrob import chart_builder as cb
from chartthrob import geometry as geo

layout = geo.ChartLayout.from_dpi(72.0)
image = cb.build_chart("Curve Export Test", layout, cb.ChartOptions())
layer = image.get_layers()[0]

spec = importlib.util.spec_from_file_location(
    "chartthrob_plugin",
    ROOT + "/plugin/chartthrob-plugin/chartthrob-plugin.py",
)
chartthrob_plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chartthrob_plugin)

pdb = Gimp.get_pdb()
analyze_proc = pdb.lookup_procedure(chartthrob_plugin.ANALYZE_PROC_NAME)
plugin_path = os.path.join(_TMP_DIR, "plugin_export.curves")
if os.path.exists(plugin_path):
    os.remove(plugin_path)


class _FakeConfig:
    def __init__(self):
        self._values = {
            "show-samples": False,
            "negate": False,
            "curve-file": Gio.File.new_for_path(plugin_path),
        }

    def get_property(self, name):
        return self._values[name]


result = chartthrob_plugin.analyze_scan_run(
    analyze_proc, Gimp.RunMode.NONINTERACTIVE, image, [layer], _FakeConfig(), None
)
assert result.index(0) == Gimp.PDBStatusType.SUCCESS
assert os.path.exists(plugin_path)
assert _field_sequence(plugin_path) == EXPECTED_FIELD_SEQUENCE
print("PLUGIN_EXPORT_OK")

image.delete()
print("MANUAL_CURVE_EXPORT_PASSED")
