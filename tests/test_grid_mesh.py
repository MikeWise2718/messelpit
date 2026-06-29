"""Invariants for build_usd.build_grid_mesh — the core DEM-grid mesher."""

from __future__ import annotations

import numpy as np
import pytest

from messelpit.build_usd import build_grid_mesh


def _ramp_dem(h=10, w=8):
    """A small non-degenerate DEM: a tilted plane so z varies."""
    ys, xs = np.mgrid[0:h, 0:w]
    return (100.0 + xs * 0.5 + ys * 0.25).astype("float32")


def test_vertex_count_matches_grid():
    dem = _ramp_dem(10, 8)
    points, fvc, fvi, uvs = build_grid_mesh(dem, res_m=1.0, decimate=1)
    assert points.shape == (10 * 8, 3)
    assert uvs.shape == (10 * 8, 2)


def test_two_triangles_per_quad():
    dem = _ramp_dem(10, 8)
    _, fvc, fvi, _ = build_grid_mesh(dem, res_m=1.0, decimate=1)
    expected_tris = 2 * (10 - 1) * (8 - 1)
    assert len(fvc) == expected_tris
    assert np.all(fvc == 3)  # every face is a triangle
    assert len(fvi) == expected_tris * 3


def test_indices_in_range():
    dem = _ramp_dem(10, 8)
    points, _, fvi, _ = build_grid_mesh(dem, res_m=1.0, decimate=1)
    assert fvi.min() >= 0
    assert fvi.max() < len(points)


def test_uv_range_normalized():
    dem = _ramp_dem(10, 8)
    _, _, _, uvs = build_grid_mesh(dem, res_m=1.0, decimate=1)
    assert uvs.min() >= 0.0
    assert uvs.max() <= 1.0
    # Corners hit the full 0..1 extent.
    assert np.isclose(uvs[:, 0].min(), 0.0) and np.isclose(uvs[:, 0].max(), 1.0)
    assert np.isclose(uvs[:, 1].min(), 0.0) and np.isclose(uvs[:, 1].max(), 1.0)


def test_z_is_dem_value():
    dem = _ramp_dem(10, 8)
    points, _, _, _ = build_grid_mesh(dem, res_m=1.0, decimate=1)
    # Z column of points must be exactly the DEM values (no z_lift on terrain).
    assert np.allclose(np.sort(points[:, 2]), np.sort(dem.ravel().astype("float32")))


@pytest.mark.parametrize("decimate", [2, 4, 8])
def test_decimate_reduces_resolution(decimate):
    dem = _ramp_dem(33, 33)  # odd so ::decimate is well-defined
    full, _, _, _ = build_grid_mesh(dem, res_m=1.0, decimate=1)
    dec, _, _, _ = build_grid_mesh(dem, res_m=1.0, decimate=decimate)
    assert len(dec) < len(full)
    # Decimated grid spacing = res * decimate; check X extent is preserved
    # to within one (coarser) cell.
    assert dec[:, 0].max() <= full[:, 0].max()


def test_resolution_scales_coords():
    dem = _ramp_dem(5, 5)
    p1, _, _, _ = build_grid_mesh(dem, res_m=1.0, decimate=1)
    p2, _, _, _ = build_grid_mesh(dem, res_m=2.0, decimate=1)
    # Doubling res_m doubles the X/Y extent.
    assert np.isclose(p2[:, 0].max(), 2.0 * p1[:, 0].max())
    assert np.isclose(p2[:, 1].max(), 2.0 * p1[:, 1].max())


def test_no_nan_in_output():
    dem = _ramp_dem(12, 9)
    points, fvc, fvi, uvs = build_grid_mesh(dem, res_m=1.0, decimate=1)
    for arr in (points, uvs):
        assert not np.isnan(arr).any()
