"""Manual proof for the padding option (a chartthrob-gimp addition, not in
the original ChartThrob.jsx -- requested by a real user of this port).

NOT collected by pytest (no `Gimp` module there; filename intentionally
doesn't match `test_*.py`). Run directly:

    scripts/run_gimp_batch.sh tests/integration/manual_padding.py

Covers: `chart_builder.add_padding()` directly, and the full plugin dialog
wiring (the `padding`/`padding-px` procedure arguments, including that
`padding=False` -- the default -- leaves the chart exactly unpadded, i.e.
this feature is opt-in and doesn't change existing behavior).
"""
import sys

sys.path.insert(0, "/Users/kendrick/Documents/CODE/ChartThrob-GIMP")

from chartthrob import chart_builder as cb
from chartthrob import geometry as geo

layout = geo.ChartLayout.from_dpi(72.0)
unpadded_width = round(layout.width)
unpadded_height = round(layout.height)

# --- Direct chart_builder.build_chart() check -------------------------------

padded_image = cb.build_chart(
    "Padding Test", layout, cb.ChartOptions(padding_px=40.0)
)
assert padded_image.get_width() == unpadded_width + 80
assert padded_image.get_height() == unpadded_height + 80
assert len(padded_image.get_layers()) == 1  # still a single flattened layer
padded_image.delete()
print("BUILD_CHART_PADDING_OK")

unpadded_image = cb.build_chart("No Padding Test", layout, cb.ChartOptions())
assert unpadded_image.get_width() == unpadded_width
assert unpadded_image.get_height() == unpadded_height
unpadded_image.delete()
print("BUILD_CHART_DEFAULT_UNPADDED_OK")

# --- Through the real plugin procedure, via the PDB -------------------------

pdb = Gimp.get_pdb()
build_proc = pdb.lookup_procedure("python-fu-chartthrob-build")
assert build_proc is not None, "plugin not registered -- is it installed/symlinked?"

before_images = set(img.get_id() for img in Gimp.get_images())

config = build_proc.create_config()
config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
config.set_property("dpi", 72.0)
config.set_property("padding", True)
config.set_property("padding-px", 40.0)
config.set_property("label", "PDB Padding Test")
result = build_proc.run(config)
assert result.index(0) == Gimp.PDBStatusType.SUCCESS

after_images = [img for img in Gimp.get_images() if img.get_id() not in before_images]
assert len(after_images) == 1
plugin_padded_image = after_images[0]
assert plugin_padded_image.get_width() == unpadded_width + 80
assert plugin_padded_image.get_height() == unpadded_height + 80
plugin_padded_image.delete()
print("PLUGIN_PADDING_OK")

print("MANUAL_PADDING_PASSED")
