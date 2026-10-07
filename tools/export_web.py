# /// script
# requires-python = ">=3.11"
# dependencies = ["pyproj>=3.6", "rasterio>=1.3", "numpy>=1.26", "rich>=13", "rich-argparse>=1.4"]
# ///
"""Export the Messel scene as a dtlite web bundle (dthub/specs/dtlite.md).

Scene knowledge stays here; the bundling is dtlite's generic `dtlite-bundle`, run from
the sibling dtlite checkout. What this adds on top:

- the schematic geological layer model (data/geology_schematic.toml, built by
  tools/geology_schematic.py) as a dtlite geology overlay;
- Krister Smith's boreholes (sibling repo messel-dt, data/v0) as a second, columns-only
  geology overlay (tools/krister_boreholes.py) -- skipped if that checkout is absent;
- the scene docs (docs/web/*.md, shown in dtlite's Docs panel) and the source list
  (docs/web/sources.json, shown in About);
- the Nix (2003) monitoring stations (docs/messel-nix-2003-stations.csv), transformed
  DHDN / Gauss-Krueger zone 3 (EPSG:31467) -> ETRS89 / UTM 32N (EPSG:25832) -> local
  scene metres (SW origin from data/prep/origin.json), written as GeoJSON.

    uv run tools/export_web.py                 # -> out/web/messel
    uv run tools/export_web.py -st 4           # finer terrain grid
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from pyproj import Transformer
from rich.console import Console
from rich_argparse import RichHelpFormatter

REPO = Path(__file__).resolve().parents[1]
DTLITE = Path(os.environ.get("DTLITE_DIR", REPO.parent / "dtlite"))
VIEWER_DATA = REPO.parent / "usd_viewer" / "data"
console = Console()


def stations_geojson(csv_path: Path, origin: dict, out_path: Path) -> int:
    """Nix stations -> GeoJSON points in local metres. z = the 2001 ground elevation (m NN)."""
    to_utm = Transformer.from_crs("EPSG:31467", "EPSG:25832", always_xy=True)
    ox, oy = origin["utm_sw_easting"], origin["utm_sw_northing"]
    feats = []
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            e, n = to_utm.transform(float(row["rechtswert_gk3"]), float(row["hochwert_gk3"]))
            z = float(row["elevation_m_nn"]) if row["elevation_m_nn"] else None
            props = {
                "name": row["name"],
                "type": row["type"],
                "elevation_m_nn_2001": z,
                "depth_m": float(row["depth_m"]) if row["depth_m"] else None,
                "remark": row["remark"] or None,
                "gk3": [int(row["rechtswert_gk3"]), int(row["hochwert_gk3"])],
            }
            coords = [round(e - ox, 2), round(n - oy, 2)] + ([z] if z is not None else [])
            feats.append({"type": "Feature", "properties": props,
                          "geometry": {"type": "Point", "coordinates": coords}})
    doc = {
        "type": "FeatureCollection",
        "dtlite": {
            "name": "stations",
            "title": "Monitoring stations (Nix 2003)",
            "tier": "open",
            "frame": "local scene metres, SW origin (UTM 32N "
                     f"{ox}/{oy}); transformed from DHDN GK3, ~1 m class",
            "source": "Nix (2003) Geol. Abh. Hessen 112, Appendix 12.1 — OCR, hand-cleaned",
        },
        "features": feats,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return len(feats)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=RichHelpFormatter)
    p.add_argument("-o", "--out", type=Path, default=REPO / "out" / "web", help="bundle output dir")
    p.add_argument("-st", "--step", type=float, default=6.0, help="terrain grid step (m)")
    p.add_argument("-tm", "--tiles", type=float, default=1.0,
                   help="finest tile cell (m) for the LOD pyramid; 0 = no tiles")
    p.add_argument("-sc", "--sidecar", type=Path, default=VIEWER_DATA / "messel_lo.usdz.viewer.json",
                   help="Kit sidecar to carry along (viewpoints etc.)")
    a = p.parse_args(argv)

    prep = REPO / "data" / "prep"
    origin = json.loads((prep / "origin.json").read_text(encoding="utf-8"))
    stage = REPO / "out" / "web_stage"
    stations = stage / "stations.geojson"
    n = stations_geojson(REPO / "docs" / "messel-nix-2003-stations.csv", origin, stations)
    console.print(f"stations: {n} points -> {stations}")

    sys.path.insert(0, str(Path(__file__).parent))
    from geology_schematic import build as build_geology
    geo = build_geology(REPO / "data" / "geology_schematic.toml", prep / "dem.tif")
    geology = stage / "messel.geology.json"
    geology.write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    console.print(f"geology: {len(geo['surfaces'])} surfaces, {len(geo['columns'])} column(s) -> {geology}")

    from krister_boreholes import SOURCE as BH_SOURCE, build as build_boreholes
    boreholes = None
    if BH_SOURCE.is_file():
        bh = build_boreholes(BH_SOURCE, prep / "dem.tif", origin)
        boreholes = stage / "messel.boreholes.json"
        boreholes.write_text(json.dumps(bh, separators=(",", ":")), encoding="utf-8")
        console.print(f"boreholes: {len(bh['columns'])} (Krister Smith v0) -> {boreholes}")
    else:
        console.print(f"[yellow]boreholes skipped[/yellow]: {BH_SOURCE} not found")

    if not DTLITE.is_dir():
        console.print(f"[red]dtlite checkout not found at {DTLITE}[/red] (set DTLITE_DIR)")
        return 2
    cmd = ["uv", "run", "--directory", str(DTLITE), "dtlite-bundle",
           "-i", "messel", "-t", "Grube Messel",
           "-d", str(prep / "dem.tif"), "-or", str(prep / "ortho.png"),
           "-st", str(a.step), "-sc", str(a.sidecar),
           "-dr", str(REPO / "out" / "messel.osm.drape.json"),
           "-gj", str(stations), "-go", str(geology),
           *(["-go", str(boreholes)] if boreholes else []),
           "-dd", str(REPO / "docs" / "web"), "-so", str(REPO / "docs" / "web" / "sources.json"),
           "-o", str(a.out.resolve())]
    if a.tiles:
        cmd += ["-tm", str(a.tiles)]
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "VIRTUAL_ENV")}
    return subprocess.run(cmd, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
