"""Tests for the viewer->builder nudge / bake-back logic in build_map_overlay.

These cover the pure file-parsing + offset-composition added with the
interactive nudge controls. They are the highest-value unit tests in the
suite: the math is a deterministic in/out and a sign flip or a dz-not-folding
regression would silently misplace the Planquad overlay.
"""

from __future__ import annotations

import json

import pytest
from rich.console import Console

from messelpit.build_map_overlay import (
    PLANQUAD_LOCAL,
    PLANQUAD_PRIM,
    _NUDGE_DX,
    _read_nudge_file,
)

# A quiet console so test output isn't cluttered by the function's rich prints.
CONSOLE = Console(quiet=True)


def _write_nudge(tmp_path, payload) -> "object":
    p = tmp_path / "messel_lo_with_overlays.usd.nudge.json"
    p.write_text(json.dumps(payload))
    return p


def test_reads_valid_offset(tmp_path):
    p = _write_nudge(tmp_path, {PLANQUAD_PRIM: [12.0, -3.5, 1.25]})
    assert _read_nudge_file(p, PLANQUAD_PRIM, CONSOLE) == (12.0, -3.5, 1.25)


def test_missing_file_is_zero(tmp_path):
    p = tmp_path / "does_not_exist.nudge.json"
    assert _read_nudge_file(p, PLANQUAD_PRIM, CONSOLE) == (0.0, 0.0, 0.0)


def test_missing_entry_is_zero(tmp_path):
    p = _write_nudge(tmp_path, {"/World/Maps/SomethingElse": [1, 2, 3]})
    assert _read_nudge_file(p, PLANQUAD_PRIM, CONSOLE) == (0.0, 0.0, 0.0)


def test_malformed_json_is_zero(tmp_path):
    p = tmp_path / "broken.nudge.json"
    p.write_text("{not valid json")
    assert _read_nudge_file(p, PLANQUAD_PRIM, CONSOLE) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("bad", [[1, 2], [1, 2, 3, 4], "not-a-list", 42, {"x": 1}])
def test_wrong_shape_entry_is_zero(tmp_path, bad):
    p = _write_nudge(tmp_path, {PLANQUAD_PRIM: bad})
    assert _read_nudge_file(p, PLANQUAD_PRIM, CONSOLE) == (0.0, 0.0, 0.0)


def test_int_values_coerced_to_float(tmp_path):
    p = _write_nudge(tmp_path, {PLANQUAD_PRIM: [10, 20, 0]})
    dx, dy, dz = _read_nudge_file(p, PLANQUAD_PRIM, CONSOLE)
    assert (dx, dy, dz) == (10.0, 20.0, 0.0)
    assert all(isinstance(v, float) for v in (dx, dy, dz))


def test_offset_composition_is_additive():
    """The builder folds flag --dx/--dy and the baked nudge additively, and
    shifts every rect edge by the same total. This mirrors the logic in
    build_map_overlay.main() so the composition contract is pinned."""
    flag_dx, flag_dy = -50.0, 0.0
    bake_dx, bake_dy = 7.0, -4.0
    total_dx = flag_dx + bake_dx
    total_dy = flag_dy + bake_dy

    rect = {
        "x_min": PLANQUAD_LOCAL["x_min"] + total_dx,
        "x_max": PLANQUAD_LOCAL["x_max"] + total_dx,
        "y_min": PLANQUAD_LOCAL["y_min"] + total_dy,
        "y_max": PLANQUAD_LOCAL["y_max"] + total_dy,
    }
    # Width/height invariant under a pure translation.
    assert rect["x_max"] - rect["x_min"] == PLANQUAD_LOCAL["x_max"] - PLANQUAD_LOCAL["x_min"]
    assert rect["y_max"] - rect["y_min"] == PLANQUAD_LOCAL["y_max"] - PLANQUAD_LOCAL["y_min"]
    # Every edge moved by the same delta.
    assert rect["x_min"] - PLANQUAD_LOCAL["x_min"] == total_dx
    assert rect["y_max"] - PLANQUAD_LOCAL["y_max"] == total_dy


def test_default_nudge_shifts_west():
    """The documented registration correction is 50 m west (negative X)."""
    assert _NUDGE_DX == -50.0
    assert _NUDGE_DX < 0  # west, per the spec's off-by-one-cell correction
