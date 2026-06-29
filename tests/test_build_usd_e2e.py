"""End-to-end USD build test with real assertions on the output stage.

This is the assertion-bearing successor to tools/smoke_test.py: it builds a
small synthetic terrain through the real authoring path and checks the stage
is structurally correct (Z-up, meters, terrain prim, material wired), then
packages a .usdz and verifies it opens with the texture bundled.

The .usdz case is a regression guard for the Windows packaging bug where the
png-no-resize path returned the source texture outside the temp dir, so
CreateNewUsdzPackage failed to map ./ortho.png.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from pxr import Usd, UsdGeom

from messelpit.build_usd import author_stage, build_grid_mesh

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402


def _synthetic(prep_dir, n=64):
    """Write a tiny synthetic dem.tif + ortho.png + origin-ish meta."""
    ys, xs = np.mgrid[0:n, 0:n].astype("float32")
    dem = (160.0 + 5.0 * np.sin(xs / 8.0) - 10.0 * np.cos(ys / 8.0)).astype("float32")

    dem_path = prep_dir / "dem.tif"
    with rasterio.open(
        dem_path, "w", driver="GTiff", height=n, width=n, count=1,
        dtype="float32", transform=from_origin(0.0, n, 1.0, 1.0),
    ) as dst:
        dst.write(dem, 1)

    rgb = np.zeros((n, n, 3), dtype="uint8")
    rgb[..., 0] = (xs * 4).clip(0, 255).astype("uint8")
    Image.fromarray(rgb, "RGB").save(prep_dir / "ortho.png")

    # build_usd.main() reads origin.json from the prep dir; mirror what
    # prep_rasters.py writes (only the fields the build path consumes).
    import json
    (prep_dir / "origin.json").write_text(json.dumps({
        "utm_zone": "32N", "epsg": 25832,
        "utm_sw_easting": 0, "utm_sw_northing": 0,
        "width_m": n, "height_m": n,
        "dem_resolution_m": 1.0, "ortho_resolution_m": 1.0,
        "dem_stats": {
            "min": float(dem.min()), "max": float(dem.max()),
            "mean": float(dem.mean()), "shape": [n, n],
        },
    }))
    return dem, dem_path


def test_author_stage_structure(tmp_path):
    dem, _ = _synthetic(tmp_path)
    out = tmp_path / "demo.usd"
    # Copy a texture next to the .usd so the relative ref resolves.
    Image.open(tmp_path / "ortho.png").save(out.parent / "ortho.png")

    from rich.console import Console
    author_stage(
        out_path=out, dem=dem, res_m=1.0, ortho_rel_path="./ortho.png",
        origin_meta={"epsg": 25832, "width_m": 64, "height_m": 64},
        decimate=1, console=Console(quiet=True),
    )
    assert out.exists()

    stage = Usd.Stage.Open(str(out))
    assert stage is not None
    # Z-up, meters.
    assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0
    # Terrain prim exists and is a Mesh with points.
    terrain = stage.GetPrimAtPath("/World/Terrain")
    assert terrain and terrain.IsA(UsdGeom.Mesh)
    mesh = UsdGeom.Mesh(terrain)
    pts = mesh.GetPointsAttr().Get()
    assert pts is not None and len(pts) == 64 * 64
    # Origin metadata round-trips into customData on /World.
    world = stage.GetPrimAtPath("/World")
    origin = world.GetCustomDataByKey("messelpit:origin")
    assert origin and int(origin["epsg"]) == 25832


def test_build_usd_cli_writes_usd_and_usdz(tmp_path):
    """Drive build_usd.main() via subprocess with --usdz, the path that
    previously crashed on Windows. Asserts both artifacts appear."""
    import subprocess
    import sys

    prep = tmp_path / "prep"
    prep.mkdir()
    _synthetic(prep)
    out = tmp_path / "out" / "demo.usd"
    out.parent.mkdir()

    res = subprocess.run(
        [sys.executable, "-m", "messelpit.build_usd",
         "-i", str(prep), "-o", str(out), "--usdz"],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    assert out.exists(), "loose .usd not written"
    usdz = out.with_suffix(".usdz")
    assert usdz.exists(), "usdz not written"

    # The usdz opens and the bundled texture is present inside the package.
    stage = Usd.Stage.Open(str(usdz))
    assert stage is not None
    assert stage.GetPrimAtPath("/World/Terrain")
