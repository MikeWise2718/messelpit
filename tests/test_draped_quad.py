"""Tests for the draped-quad overlay geometry (build_map_overlay)."""

from __future__ import annotations

import numpy as np

from messelpit.build_map_overlay import _sample_dem, build_draped_quad


def _flat_dem(h=100, w=100, z=170.0):
    return np.full((h, w), z, dtype="float32")


def test_sample_dem_flat_returns_constant():
    dem = _flat_dem(z=170.0)
    xs = np.array([0.0, 10.0, 50.0, 99.0])
    ys = np.array([0.0, 10.0, 50.0, 99.0])
    z = _sample_dem(dem, 1.0, xs, ys)
    assert np.allclose(z, 170.0)


def test_sample_dem_clamps_out_of_range():
    dem = _flat_dem(50, 50, z=120.0)
    # Coords well outside the grid must clamp, not raise / index-error.
    xs = np.array([-100.0, 9999.0])
    ys = np.array([-100.0, 9999.0])
    z = _sample_dem(dem, 1.0, xs, ys)
    assert np.allclose(z, 120.0)
    assert not np.isnan(z).any()


def test_draped_quad_vertex_count():
    dem = _flat_dem()
    rect = {"x_min": 10.0, "x_max": 60.0, "y_min": 10.0, "y_max": 60.0}
    subdiv = 8
    points, fvc, fvi, uvs = build_draped_quad(dem, 1.0, rect, subdiv, z_lift=1.5)
    n = subdiv + 1
    assert points.shape == (n * n, 3)
    assert uvs.shape == (n * n, 2)
    assert len(fvc) == 2 * subdiv * subdiv  # two tris per cell


def test_draped_quad_z_lift_applied():
    dem = _flat_dem(z=170.0)
    rect = {"x_min": 10.0, "x_max": 60.0, "y_min": 10.0, "y_max": 60.0}
    z_lift = 1.5
    points, _, _, _ = build_draped_quad(dem, 1.0, rect, subdiv=8, z_lift=z_lift)
    # On a flat DEM every vertex sits exactly z_lift above the surface.
    assert np.allclose(points[:, 2], 170.0 + z_lift)


def test_draped_quad_xy_within_rect():
    dem = _flat_dem()
    rect = {"x_min": 10.0, "x_max": 60.0, "y_min": 20.0, "y_max": 70.0}
    points, _, _, _ = build_draped_quad(dem, 1.0, rect, subdiv=8, z_lift=1.5)
    assert np.isclose(points[:, 0].min(), rect["x_min"])
    assert np.isclose(points[:, 0].max(), rect["x_max"])
    assert np.isclose(points[:, 1].min(), rect["y_min"])
    assert np.isclose(points[:, 1].max(), rect["y_max"])


def test_draped_quad_uv_normalized():
    dem = _flat_dem()
    rect = {"x_min": 10.0, "x_max": 60.0, "y_min": 10.0, "y_max": 60.0}
    _, _, _, uvs = build_draped_quad(dem, 1.0, rect, subdiv=8, z_lift=1.5)
    assert uvs.min() >= 0.0 and uvs.max() <= 1.0
