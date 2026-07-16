"""Unit tests for chartthrob.geometry.

Covers: DPI clamping/scaling, patch-bounds formulas for both the build-time
grid and the scan-time sampling grid, and the two fill-value formulas.
"""
from __future__ import annotations

import pytest

from chartthrob import geometry as geo


def test_clamp_dpi_leaves_valid_values_untouched():
    assert geo.clamp_dpi(300.0) == 300.0
    assert geo.clamp_dpi(72.0) == 72.0


def test_clamp_dpi_floors_low_values_to_72():
    assert geo.clamp_dpi(10.0) == 72.0
    assert geo.clamp_dpi(0.0) == 72.0
    assert geo.clamp_dpi(-500.0) == 72.0


def test_chart_layout_at_base_dpi_matches_original_globals():
    layout = geo.ChartLayout.from_dpi(300.0)
    assert layout.width == 1200.0
    assert layout.height == 1210.0
    assert layout.x_marg == 6.0
    assert layout.y_marg == 75.0
    assert layout.patch == 100.0
    assert layout.strip_width == 85.0
    assert layout.grad_width == 50.0
    # gX21 = gXMarg*2 + 10*gPatch = 12 + 1000 = 1012
    assert layout.x21 == 1012.0
    # gXGrad = gX21 + gStripWidth = 1012 + 85 = 1097
    assert layout.x_grad == 1097.0
    # gXBar = gXGrad + gGradWidth = 1097 + 50 = 1147
    assert layout.x_bar == 1147.0


@pytest.mark.parametrize("dpi", [72.0, 150.0, 300.0, 600.0, 1200.0])
def test_chart_layout_scaling_preserves_ratios(dpi):
    base = geo.ChartLayout.from_dpi(300.0)
    scaled = geo.ChartLayout.from_dpi(dpi)
    scale = dpi / 300.0
    assert scaled.width == pytest.approx(base.width * scale)
    assert scaled.height == pytest.approx(base.height * scale)
    assert scaled.patch == pytest.approx(base.patch * scale)
    # ratios independent of DPI
    assert scaled.x21 / scaled.width == pytest.approx(base.x21 / base.width)
    assert scaled.patch / scaled.width == pytest.approx(base.patch / base.width)


def test_chart_layout_from_dpi_clamps_low_dpi():
    layout = geo.ChartLayout.from_dpi(10.0)
    assert layout.dpi == 72.0
    assert layout.dpi_scale == pytest.approx(72.0 / 300.0)


def test_patch_bounds_101_first_cell():
    layout = geo.ChartLayout.from_dpi(300.0)
    b = layout.patch_bounds_101(0, 0)
    assert b.left == 6.0
    assert b.right == 106.0
    assert b.bottom == 75.0
    assert b.top == 175.0


def test_patch_bounds_101_last_grid_cell():
    layout = geo.ChartLayout.from_dpi(300.0)
    b = layout.patch_bounds_101(9, 9)
    assert b.left == 6.0 + 9 * 100.0
    assert b.right == 6.0 + 10 * 100.0
    assert b.bottom == 75.0 + 9 * 100.0
    assert b.top == 75.0 + 10 * 100.0


def test_patch_bounds_101_extra_black_patch_row():
    # j=10, i=0 is the extra pure-black patch drawn below the 10x10 grid.
    layout = geo.ChartLayout.from_dpi(300.0)
    b = layout.patch_bounds_101(0, 10)
    assert b.bottom == 75.0 + 10 * 100.0
    assert b.top == 75.0 + 11 * 100.0


def test_patch_bounds_21_endpoints():
    layout = geo.ChartLayout.from_dpi(300.0)
    ht = layout.height / 21.0
    b0 = layout.patch_bounds_21(0)
    assert b0.bottom == 0.0
    assert b0.top == pytest.approx(ht + 1)
    b20 = layout.patch_bounds_21(20)
    assert b20.bottom == pytest.approx(20 * ht)
    assert b20.left == layout.x21
    assert b20.right == layout.x21 + layout.strip_width


def test_bounds_to_polygon_order():
    b = geo.Bounds(left=1, right=2, bottom=3, top=4)
    assert b.to_polygon() == [(1, 3), (2, 3), (2, 4), (1, 4)]


def test_value_101_endpoints():
    assert geo.value_101(0) == 255
    assert geo.value_101(100) == 0


def test_value_101_midpoint():
    # n=50 -> 255 - 255*0.5 = 127.5 -> round_half_up -> 128
    assert geo.value_101(50) == 128


def test_value_21_endpoints():
    assert geo.value_21(0) == 255
    assert geo.value_21(20) == 0


def test_patch_center_matches_border_fraction_formula():
    w, h = 2000.0, 2000.0
    rw = w * (1.0 - (geo.BORDER_RIGHT + geo.BORDER_LEFT))
    rh = h * (1.0 - (geo.BORDER_TOP + geo.BORDER_BOTTOM))
    expected_x = round(w * geo.BORDER_LEFT + rw * (0.5 / 10.0))
    expected_y = round(h * geo.BORDER_TOP + rh * (0.5 / 11.0))
    px, py = geo.patch_center(w, h, 0, 0)
    assert px == pytest.approx(expected_x, abs=1)
    assert py == pytest.approx(expected_y, abs=1)


def test_patch_center_is_within_image_bounds():
    w, h = 3000.0, 3200.0
    for i in range(10):
        for j in range(11):
            px, py = geo.patch_center(w, h, i, j)
            assert 0 <= px <= w
            assert 0 <= py <= h


def test_patch_sample_bounds_centered_on_patch_center():
    w, h = 2500.0, 2600.0
    cx, cy = geo.patch_center(w, h, 3, 4)
    b = geo.patch_sample_bounds(w, h, 3, 4)
    assert (b.left + b.right) / 2.0 == pytest.approx(cx)
    assert (b.bottom + b.top) / 2.0 == pytest.approx(cy)
    # sample region must be smaller than one full patch cell
    assert (b.right - b.left) < (w / 10.0)
    assert (b.top - b.bottom) < (h / 11.0)
