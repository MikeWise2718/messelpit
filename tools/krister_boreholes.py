# /// script
# requires-python = ">=3.11"
# dependencies = ["pyproj>=3.6", "rasterio>=1.3", "numpy>=1.26", "rich>=13", "rich-argparse>=1.4"]
# ///
"""Krister Smith's boreholes (messel-dt v0) -> a dtlite geology overlay of columns.

Source: the sibling repo `messel-dt` (github.com/kristerSmith/messel-dt, private),
`data/v0/surface_points.csv`: GemPy contacts per hole, DHDN / Gauss-Krueger zone 3
(EPSG:31467), heights m NN. Formations there mark the BASE of a unit:

    MiddleMessel  base of the Middle Messel-Fm (the oil shale)
    LowerMessel   base of the Lower Messel-Fm  (= base of the lake fill)
    Basement      top of the basement / diatreme

The v0 export has no collar heights, so each column starts at TODAY's ground (DGM1);
where a contact lies above today's ground it was mined away and that part is not drawn.
FB 2001 is left out: the schematic geology layer draws it with its full log.

    uv run tools/krister_boreholes.py            # -> out/web_stage/messel.boreholes.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich_argparse import RichHelpFormatter

REPO = Path(__file__).resolve().parents[1]
MESSEL_DT = REPO.parent / "messel-dt"
SOURCE = MESSEL_DT / "data" / "v0" / "surface_points.csv"
SKIP = {"FB2001", "FB 2001"}

# (contact, the unit ABOVE it, colour) in top-down order; colours as the schematic layer
UNITS = [
    ("MiddleMessel", "Middle Messel-Fm: oil shale", "#3d3a35"),
    ("LowerMessel", "Lower Messel-Fm (breccias, sands, silts)", "#9a7650"),
    ("Basement", "below the lake fill, above the basement / diatreme", "#b3a77c"),
]
console = Console()


def build(source: Path, dem: Path, origin: dict) -> dict:
    import rasterio
    from pyproj import Transformer

    to_utm = Transformer.from_crs("EPSG:31467", "EPSG:25832", always_xy=True)
    ox, oy = origin["utm_sw_easting"], origin["utm_sw_northing"]
    holes = defaultdict(dict)
    xy = {}
    with source.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["hole"].strip()
            if name in SKIP:
                continue
            holes[name][row["formation"]] = float(row["Z"])
            xy[name] = (float(row["X"]), float(row["Y"]))

    columns = []
    with rasterio.open(dem) as src:
        band = src.read(1)
        for name in sorted(holes):
            e, n = to_utm.transform(*xy[name])
            x, y = e - ox, n - oy
            i, j = src.index(x, y)
            ground = float(band[i, j])
            segs, top = [], ground
            for key, unit, color in UNITS:
                base = holes[name].get(key)
                if base is None:
                    continue
                if base < top:  # above today's ground = mined away: nothing to draw
                    segs.append({"from_m": round(ground - top, 2), "to_m": round(ground - base, 2),
                                 "unit": unit, "color": color})
                    top = base
            if not segs:
                continue
            picks = ", ".join(f"{k} base {v:.1f} m NN" if k != "Basement" else f"basement top {v:.1f} m NN"
                              for k, v in holes[name].items())
            columns.append({
                "id": f"smith:{name}", "title": f"Borehole {name}", "x": round(x, 2), "y": round(y, 2),
                "ground_z": round(ground, 2), "radius_m": 4.0,
                "note": f"Krister Smith, borehole database v0 (messel-dt): {picks}. "
                        "Drawn from today's ground; the drill collar is not in v0.",
                "segments": segs,
            })
    return {
        "dtlite": {"name": "boreholes", "title": f"Boreholes (Krister Smith, v0: {len(columns)})",
                   "tier": "restricted",
                   "source": "Krister Smith, Messel borehole database v0 (github.com/kristerSmith/messel-dt, "
                             "data/v0/surface_points.csv; private test snapshot)"},
        "grid": None, "surfaces": [], "columns": columns,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=RichHelpFormatter)
    p.add_argument("-o", "--out", type=Path, default=REPO / "out" / "web_stage" / "messel.boreholes.json")
    a = p.parse_args(argv)
    if not SOURCE.is_file():
        console.print(f"[red]not found:[/red] {SOURCE} (clone kristerSmith/messel-dt beside messelpit)")
        return 2
    origin = json.loads((REPO / "data" / "prep" / "origin.json").read_text(encoding="utf-8"))
    doc = build(SOURCE, REPO / "data" / "prep" / "dem.tif", origin)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    console.print(f"{len(doc['columns'])} boreholes -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
