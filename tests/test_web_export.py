"""The dtlite web export's scene pieces: the schematic geology model, Krister Smith's
boreholes, and the Nix (2003) stations.

Uses the real config files (data/geology_schematic.toml, docs/messel-nix-2003-stations.csv)
over a synthetic flat DEM, so it runs without the gitignored prepped rasters.
"""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("pyproj")
from rasterio.transform import from_origin  # noqa: E402

import export_web  # noqa: E402
import krister_boreholes  # noqa: E402
from geology_schematic import build as build_geology  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ORIGIN = {"utm_sw_easting": 480000.0, "utm_sw_northing": 5526000.0}
GROUND = 150.0


@pytest.fixture
def dem(tmp_path):
    """The scene's 6 x 9 km extent in local metres, 50 m pixels, flat at 150 m."""
    path = tmp_path / "dem.tif"
    z = np.full((180, 120), GROUND, dtype="float32")
    with rasterio.open(path, "w", driver="GTiff", width=120, height=180, count=1,
                       dtype="float32", transform=from_origin(0, 9000, 50, 50)) as dst:
        dst.write(z, 1)
    return path


# ---------------------------------------------------------------- schematic geology
@pytest.fixture
def geo(dem):
    return build_geology(REPO / "data" / "geology_schematic.toml", dem)


def test_fb2001_at_krister_smiths_position(geo):
    col = geo["columns"][0]
    assert col["id"] == "fb2001"
    # GK3 R 3482757.75 / H 5531296.42 (messel-dt v0) -> UTM 32N -> local
    assert (col["x"], col["y"]) == pytest.approx((2689.6, 3523.4), abs=0.5)
    bounds = [(s["from_m"], s["to_m"]) for s in col["segments"]]
    assert bounds[0] == (0, 94) and bounds[-1] == (373, 433)
    assert all(a[1] == b[0] for a, b in zip(bounds, bounds[1:])), "segments must be contiguous"


def test_only_the_pre_mining_lid_starts_hidden(geo):
    hidden = [s["id"] for s in geo["surfaces"] if s.get("default_hidden")]
    assert hidden == ["pre_mining_ground"]


def test_surfaces_are_nested(geo):
    """Each sheet lies below the one above it wherever both exist (the viewer's fixed
    blending order and the section fills rely on it)."""
    surfs = geo["surfaces"]
    for upper, lower in zip(surfs, surfs[1:]):
        pairs = [(u, l) for u, l in zip(upper["z"], lower["z"]) if u is not None and l is not None]
        assert pairs, f"{upper['id']} and {lower['id']} never overlap"
        assert all(u >= l for u, l in pairs), f"{lower['id']} rises above {upper['id']}"


def test_centre_heights_match_fb2001(geo):
    """At the low (= FB 2001) the sheet heights follow the 105.9 m collar and its log."""
    z = {s["id"]: s for s in geo["surfaces"]}
    g = geo["grid"]
    col = geo["columns"][0]
    i = round((col["x"] - g["x0"]) / g["dx"])
    j = round((g["y_top"] - col["y"]) / g["dx"])
    at = lambda sid: z[sid]["z"][j * g["nx"] + i]
    assert at("top_lower_fm") == pytest.approx(105.9 - 94, abs=1.0)
    assert at("top_tuffite") == pytest.approx(105.9 - 228, abs=1.0)


# ---------------------------------------------------------------- Krister's boreholes
def _points(tmp_path, rows):
    path = tmp_path / "surface_points.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["X", "Y", "Z", "formation", "hole"])
        w.writerows(rows)
    return path


def test_boreholes_columns_from_contacts(tmp_path, dem):
    src = _points(tmp_path, [
        (3482581.0, 5531255.0, 19.73, "MiddleMessel", "FB 4"),
        (3482581.0, 5531255.0, -58.3, "LowerMessel", "FB 4"),
        (3482581.0, 5531255.0, -61.3, "Basement", "FB 4"),
        (3482757.75, 5531296.42, 11.9, "MiddleMessel", "FB2001"),       # left out
        (3482460.0, 5531451.0, 160.0, "MiddleMessel", "X 1"),           # above ground: mined
        (3482460.0, 5531451.0, 100.0, "LowerMessel", "X 1"),
    ])
    doc = krister_boreholes.build(src, dem, ORIGIN)
    cols = {c["title"]: c for c in doc["columns"]}
    assert set(cols) == {"Borehole FB 4", "Borehole X 1"}
    fb4 = [(s["from_m"], s["to_m"]) for s in cols["Borehole FB 4"]["segments"]]
    assert fb4 == [(0.0, GROUND - 19.73), (GROUND - 19.73, GROUND + 58.3), (GROUND + 58.3, GROUND + 61.3)]
    # the oil-shale base lies above today's ground: only the Lower Fm is drawn, from the top
    x1 = cols["Borehole X 1"]["segments"]
    assert len(x1) == 1 and x1[0]["from_m"] == 0.0 and x1[0]["unit"].startswith("Lower")
    assert doc["surfaces"] == [] and doc["dtlite"]["name"] == "boreholes"


# ---------------------------------------------------------------- Nix stations
def test_stations_geojson_and_the_in23_flag(tmp_path):
    out = tmp_path / "stations.geojson"
    n = export_web.stations_geojson(REPO / "docs" / "messel-nix-2003-stations.csv", ORIGIN, out)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert n == len(doc["features"]) == 171
    in23 = next(f for f in doc["features"] if f["properties"]["name"] == "IN23")
    assert in23["properties"]["elevation_m_nn_2001"] == 116.18          # kept as printed
    assert "misprint in Nix" in in23["properties"]["remark"]
    x, y = in23["geometry"]["coordinates"][:2]
    assert 0 < x < 6000 and 0 < y < 9000
