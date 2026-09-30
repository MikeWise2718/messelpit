"""Build the schematic Messel layer model (data/geology_schematic.toml) as a dtlite
geology overlay: gridded surfaces clipped to the maar funnel, plus the FB 2001 column.

Imported by tools/export_web.py (which runs it under its own inline-script deps); it
needs numpy and rasterio only to read the DGM1 height at the borehole.

Output format (dtlite "geology" overlay, local metres, m NN):
  { "dtlite": {...}, "grid": {x0, y_top, dx, nx, ny},            # row 0 = north
    "surfaces": [{id, title, unit, color, note, z: [nx*ny | null], max_thickness_m?, default_hidden?}],
    "fills": {ground_unit, frame, section_bottom_m_nn},     # for section cuts
    "columns": [{id, title, x, y, ground_z, radius_m, note, segments: [...]}] }
"""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

GRID_M = 10.0


def build(toml_path: Path, dem_path: Path) -> dict:
    import numpy as np
    import rasterio

    cfg = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    dep, st = cfg["deposit"], cfg["structure"]
    cx, cy = dep["centre"]
    a, b = dep["semi_axes_m"]
    th = math.radians(dep["bearing_deg"])
    lx, ly = st["low"]
    r_eff = math.sqrt(a * b)
    tan_dip = math.tan(math.radians(st["dip_at_rim_deg"]))
    tan_wall = math.tan(math.radians(dep["wall_angle_deg"]))
    top = dep["top_m_nn"]

    # grid over the ellipse's bounding square (+ margin)
    half = max(a, b) + 2 * GRID_M
    x0, y_top = cx - half, cy + half
    n = int(math.ceil(2 * half / GRID_M)) + 1
    xs = x0 + np.arange(n) * GRID_M
    ys = y_top - np.arange(n) * GRID_M
    X, Y = np.meshgrid(xs, ys)

    def rho_about(px, py):
        """Normalised ellipse radius of every grid node, measured from (px, py) —
        the ellipse keeps its axes but is re-centred, so rho = 0 at the low and 1 on
        the (shifted) outline; outside-the-deposit is decided separately."""
        dx, dy = X - px, Y - py
        u = dx * math.cos(th) + dy * math.sin(th)
        v = -dx * math.sin(th) + dy * math.cos(th)
        return np.sqrt((u / a) ** 2 + (v / b) ** 2)

    rho_dep = rho_about(cx, cy)            # inside the deposit outline: <= 1
    rho_low = rho_about(lx, ly)            # distance from the structural low
    A = tan_dip * r_eff / 2                # slope at rho = 1 equals tan(dip)

    surfaces = []
    for s in cfg["surface"]:
        if s["kind"] == "flat":
            z = np.full(X.shape, s["z"], dtype=float)
            inside = rho_dep <= 1.0
        elif s["kind"] == "bowl":
            z = s["z_centre"] + A * rho_low ** 2
            # the fill narrows with depth: at elevation z the outline has shrunk by
            # (top - z) / tan(wall), as a fraction of the mean radius
            shrink = np.clip((top - z) / tan_wall / r_eff, 0, 1)
            inside = rho_dep <= 1.0 - shrink
        elif s["kind"] == "pipe":
            z = np.full(X.shape, s["z_centre"], dtype=float)
            inside = rho_low <= s["pipe_fraction"]
        else:
            raise ValueError(f"unknown surface kind {s['kind']!r}")
        zs = [round(float(v), 2) if ok else None for v, ok in zip(z.ravel(), inside.ravel())]
        out = {k: s[k] for k in ("id", "title", "unit", "color", "note")} | {"z": zs}
        if "max_thickness_m" in s:
            out["max_thickness_m"] = s["max_thickness_m"]
        if s.get("default_hidden"):
            out["default_hidden"] = True   # the viewer starts with this sheet switched off
        surfaces.append(out)

    with rasterio.open(dem_path) as src:
        row, col = src.index(lx, ly)
        ground = float(src.read(1, window=((row, row + 1), (col, col + 1)))[0, 0])
    col_cfg = cfg["column"]
    column = {k: col_cfg[k] for k in ("id", "title", "radius_m", "note")} | {
        "x": lx, "y": ly, "ground_z": round(ground, 2), "segments": col_cfg["segments"]}

    return {
        "dtlite": {
            "name": "geology",
            "title": "Geology (schematic)",
            "tier": "open",
            "schematic": True,
            "note": "Schematic layer model: elevations from Nix (2003), shapes parametric. "
                    "Not a borehole interpolation. Params: messelpit/data/geology_schematic.toml",
        },
        "grid": {"x0": x0, "y_top": y_top, "dx": GRID_M, "nx": n, "ny": n},
        "surfaces": surfaces,
        "columns": [column],
        "fills": cfg["fills"],
    }
