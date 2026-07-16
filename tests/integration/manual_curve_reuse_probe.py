"""Manual probe: can one Gimp.Curve object be reused across images?

NOT collected by pytest (no `Gimp` module there; filename intentionally
doesn't match `test_*.py`). Run directly:

    scripts/run_gimp_batch.sh tests/integration/manual_curve_reuse_probe.py

This backs PLAN.md section 4.2: confirms that a single `Gimp.Curve` object
can be attached to `Gimp.DrawableFilter`s on two *different* images within
the same GIMP session and produce identical results, without rebuilding
the curve from its raw point list each time. This only covers same-session
reuse -- there's still no scriptable way to save/load a Curve to persist it
across separate GIMP sessions (see PLAN.md section 4.1 item 6).
"""
babl_srgb = Babl.format("R'G'B'A float")


def gray(value):
    c = Gegl.Color.new("black")
    v = value / 255.0
    c.set_rgba_with_space(v, v, v, 1.0, babl_srgb)
    return c


def mean_of(layer):
    ok, mean, sd, med, px, ct, pct = layer.histogram(Gimp.HistogramChannel.RED, 0.0, 1.0)
    return mean


# Build ONE curve object.
curve = Gimp.Curve.new()
curve.set_curve_type(Gimp.CurveType.SMOOTH)
curve.clear_points()
for x, y in [(0.0, 0.0), (128.0, 200.0), (255.0, 255.0)]:
    curve.add_point(x / 255.0, y / 255.0)

results = []
for label, test_value in [("image_A", 128.0), ("image_B", 128.0)]:
    image = Gimp.Image.new(4, 4, Gimp.ImageBaseType.RGB)
    layer = Gimp.Layer.new(image, "p", 4, 4, Gimp.ImageType.RGB_IMAGE, 100.0, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, None, 0)
    Gimp.context_set_foreground(gray(test_value))
    layer.edit_fill(Gimp.FillType.FOREGROUND)

    f = Gimp.DrawableFilter.new(layer, "gimp:curves", "reused-curve-test")
    config = f.get_config()
    config.set_property("channel", Gimp.HistogramChannel.VALUE)
    config.set_property("trc", Gimp.TRCType.NON_LINEAR)
    config.set_property("curve", curve)  # SAME curve object, second time around
    f.update()
    layer.merge_filter(f)

    result = mean_of(layer)
    results.append(result)
    print(f"{label}: applied same Curve object -> {result:.2f}")
    image.delete()

assert results[0] == results[1], "same curve object gave different results on two images!"
print("CURVE_REUSE_OK")
