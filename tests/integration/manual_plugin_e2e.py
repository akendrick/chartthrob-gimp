"""Manual Phase 4 proof: the plugin registers with GIMP's PDB and both
procedures work end-to-end.

NOT collected by pytest (no `Gimp` module there; filename intentionally
doesn't match `test_*.py`). Requires the plugin to be installed first
(symlink `plugin/chartthrob-plugin` into GIMP's plug-ins directory -- see
`plugin/chartthrob-plugin/chartthrob-plugin.py`'s module docstring). Run:

    scripts/run_gimp_batch.sh tests/integration/manual_plugin_e2e.py

KNOWN HARNESS LIMITATION, DOCUMENTED RATHER THAN WORKED AROUND: GIMP 3's
Python bindings do not currently support setting a `GimpCoreObjectArray`
-typed `ProcedureConfig` property (the implicit "drawables" argument on
every `Gimp.ImageProcedure`) via generic `set_property()` -- confirmed
against real GIMP 3.2.4 with both a list and a tuple, both raising the
identical `TypeError: could not convert ... to type 'GimpCoreObjectArray'`.
This blocks driving `python-fu-chartthrob-analyze` through a *fully*
PDB-marshaled call in a headless script. It does NOT block real usage:
GIMP's own menu dispatch supplies `image`/`drawables` as native arguments
directly, without this property-marshaling path, exactly the way
`foggify.py` (bundled with GIMP) receives them.

So this test proves two different but complementary things:
  1. The BUILD procedure end-to-end through the *real* PDB call path
     (`run(config)`), including menu registration, config defaults, and
     `Gimp.Display.new()`'s headless-safe fallback.
  2. The ANALYZE procedure's actual `analyze_scan_run()` function, called
     directly with a real image/drawable and a minimal stand-in config
     object -- exercising the real plugin code (config reads, ScanOptions
     construction, calling the already-proven `chart_analyzer.analyze_chart`,
     error handling) without needing the one GI-array-property path that
     doesn't work standalone. `procedure.new_return_values()` is still
     called against a real, PDB-looked-up procedure object.
"""
import sys

sys.path.insert(0, "/Users/kendrick/Documents/CODE/ChartThrob-GIMP")
sys.path.insert(0, "/Users/kendrick/Documents/CODE/ChartThrob-GIMP/plugin/chartthrob-plugin")

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "chartthrob_plugin",
    "/Users/kendrick/Documents/CODE/ChartThrob-GIMP/plugin/chartthrob-plugin/chartthrob-plugin.py",
)
chartthrob_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chartthrob_plugin)

pdb = Gimp.get_pdb()

# --- Registration -----------------------------------------------------------

assert pdb.procedure_exists(chartthrob_plugin.BUILD_PROC_NAME)
assert pdb.procedure_exists(chartthrob_plugin.ANALYZE_PROC_NAME)
print("REGISTRATION_OK")

# --- Build procedure, through the real PDB call path ------------------------

before_images = set(img.get_id() for img in Gimp.get_images())

build_proc = pdb.lookup_procedure(chartthrob_plugin.BUILD_PROC_NAME)
build_config = build_proc.create_config()
build_config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
build_config.set_property("dpi", 72.0)
build_config.set_property("numbers", False)
build_config.set_property("outlines", True)
build_config.set_property("label", "Plugin E2E Test")
build_result = build_proc.run(build_config)
assert build_result.index(0) == Gimp.PDBStatusType.SUCCESS, build_result.index(0)

after_images = [img for img in Gimp.get_images() if img.get_id() not in before_images]
assert len(after_images) == 1, f"expected exactly one new image, got {len(after_images)}"
image = after_images[0]
assert image.get_width() == 288 and image.get_height() == 290
print("BUILD_PROC_OK")

# --- Analyze procedure's actual wrapper function, called directly ----------


class _FakeConfig:
    def __init__(self, show_samples: bool, negate: bool):
        self._values = {"show-samples": show_samples, "negate": negate}

    def get_property(self, name):
        return self._values[name]


layer = image.get_layers()[0]
analyze_proc = pdb.lookup_procedure(chartthrob_plugin.ANALYZE_PROC_NAME)
config = _FakeConfig(show_samples=False, negate=False)

result = chartthrob_plugin.analyze_scan_run(
    analyze_proc, Gimp.RunMode.NONINTERACTIVE, image, [layer], config, None
)
assert result.index(0) == Gimp.PDBStatusType.SUCCESS, result.index(0)

filters = layer.get_filters()
assert len(filters) == 1, f"expected exactly one filter, got {len(filters)}"
assert filters[0].get_name() == "Print Curve"
assert filters[0].get_visible() is False
print("ANALYZE_PROC_OK")

image.delete()
print("MANUAL_PLUGIN_E2E_PASSED")
