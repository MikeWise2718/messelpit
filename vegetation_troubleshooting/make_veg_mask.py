"""Generate a vegetation mask from the DOP20 NIR band (band 4).

Uses NDVI = (NIR - R) / (NIR + R) to isolate trees and vegetation.
Output is a white-on-black PNG at DEM resolution (1 m/px):
  white = vegetation / canopy (will be interpolated in smooth_dem.py)
  black = bare ground / roads / buildings / water

Edit the output in GIMP or Photoshop before running smooth_dem.py:
  - Paint white over any extra bumps you want smoothed
  - Paint black over false positives (rooftops, bright fields, etc.)

Inputs:
  data/raw/dop20/          raw RGBI tiles
  data/prep/origin.json    bbox (written by prep_rasters.py)

Output:
  data/prep/veg_mask.png   white = smooth here, black = keep as-is
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.merge import merge
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rich.console import Console
from rich_argparse import RichHelpFormatter

HESSEN_CRS = CRS.from_epsg(25832)


def _open_with_crs(path: Path):
    src = rasterio.open(path)
    if src.crs is None:
        return WarpedVRT(src, src_crs=HESSEN_CRS, crs=HESSEN_CRS)
    return src


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="make_veg_mask", description=__doc__,
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("-i", "--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("-p", "--prep-dir", type=Path, default=Path("data/prep"))
    parser.add_argument("-o", "--out", type=Path,
                        default=Path("vegetation_troubleshooting/veg_mask.png"),
                        help="Output mask PNG (default: vegetation_troubleshooting/veg_mask.png)")
    parser.add_argument("--threshold", "-t", type=float, default=0.15,
                        help="NDVI threshold above which a pixel is 'vegetation' "
                             "(0–1, default 0.15). Lower = more vegetation detected.")
    parser.add_argument("--dilate", type=int, default=3,
                        help="Dilation radius in pixels to expand mask edges (default 3).")
    args = parser.parse_args()

    console = Console()
    out_path = args.out or (args.prep_dir / "veg_mask.png")

    origin_file = args.prep_dir / "origin.json"
    if not origin_file.exists():
        console.print("[red]origin.json not found[/red] — run prep_rasters.py first")
        raise SystemExit(1)

    origin = json.loads(origin_file.read_text())
    e0 = origin["utm_sw_easting"]
    n0 = origin["utm_sw_northing"]
    w = origin["width_m"]
    h = origin["height_m"]
    bbox = (e0, n0, e0 + w, n0 + h)
    # Match ortho pixel dimensions so mask overlays 1:1 in Krita
    ortho_dims = origin.get("ortho_dims_px")
    if ortho_dims:
        out_w, out_h = ortho_dims
    else:
        out_w, out_h = int(w), int(h)  # fall back to DEM resolution

    dop_dir = args.raw_dir / "dop20"
    tiles = sorted(dop_dir.glob("*.jpg")) + sorted(dop_dir.glob("*.tif"))
    if not tiles:
        console.print(f"[red]No DOP20 tiles found in {dop_dir}[/red]")
        raise SystemExit(1)
    console.print(f"[cyan]DOP20:[/cyan] opening {len(tiles)} tiles")

    sources = [_open_with_crs(t) for t in tiles]
    n_bands = sources[0].count
    if n_bands < 4:
        console.print(
            f"[yellow]Warning:[/yellow] DOP20 tiles have {n_bands} bands — "
            "need 4 (RGBI) for NDVI. Falling back to greenness index (G - R).")

    mosaic, _ = merge(sources, bounds=bbox)
    for s in sources:
        s.close()

    r = mosaic[0].astype("float32")
    if n_bands >= 4:
        nir = mosaic[3].astype("float32")
        denom = nir + r
        denom = np.where(denom == 0, 1e-6, denom)
        index = (nir - r) / denom
        index_name = "NDVI"
    else:
        g = mosaic[1].astype("float32")
        index = (g - r) / (g + r + 1e-6)
        index_name = "greenness"

    console.print(f"[cyan]{index_name} range:[/cyan] "
                  f"{index.min():.3f} .. {index.max():.3f}  "
                  f"(threshold={args.threshold})")

    mask = (index >= args.threshold).astype("uint8")
    veg_frac = mask.mean() * 100
    console.print(f"[cyan]Vegetation pixels:[/cyan] {veg_frac:.1f}%")

    if args.dilate > 0:
        from scipy.ndimage import binary_dilation
        struct = np.ones((args.dilate * 2 + 1, args.dilate * 2 + 1), dtype=bool)
        mask = binary_dilation(mask.astype(bool), structure=struct).astype("uint8")
        console.print(f"[cyan]After dilation ({args.dilate}px):[/cyan] "
                      f"{mask.mean()*100:.1f}% vegetation")

    # Resample to ortho resolution so mask overlays 1:1 in Krita
    img_native = Image.fromarray(mask * 255, mode="L")
    img_out = img_native.resize((out_w, out_h), Image.NEAREST)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    img_out.save(out_path)
    console.print(f"[green]wrote[/green] {out_path}  ({out_w}x{out_h} px)")
    console.print(
        "\nEdit in GIMP/Photoshop: [white]=smooth here[/white], [black]=keep as-is"
        "\nThen run: [cyan]uv run tools/smooth_dem.py[/cyan]")


if __name__ == "__main__":
    main()
