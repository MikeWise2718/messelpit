"""Generate a vegetation mask combining colour and DEM height-anomaly signals.

Two complementary detectors are computed and OR-ed together:

1. Colour index (greenness or NDVI)
   Uses NDVI = (NIR-R)/(NIR+R) when band 4 is available, otherwise falls back to
   the greenness index (G-R)/(G+R). Catches well-lit, high-greenness canopy.

2. Height anomaly (--ha-sigma / --ha-threshold flags)
   Compares each DEM pixel to a Gaussian-smoothed version of the DEM. Pixels that
   sit more than N metres above the local average are flagged as canopy hits. This
   catches trees regardless of colour — useful for shadowed or low-greenness species.

Output is a white-on-black PNG matched to ortho resolution:
  white = vegetation / canopy (will be interpolated in smooth_dem.py)
  black = bare ground / roads / buildings / water

Inputs:
  data/raw/dop20/          raw RGBI tiles
  data/prep/dem.tif        DEM (written by prep_rasters.py) — for height anomaly
  data/prep/origin.json    bbox (written by prep_rasters.py)

Output:
  vegetation_troubleshooting/veg_mask.png
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
    parser.add_argument("--ha-sigma", type=float, default=30.0,
                        help="Gaussian blur sigma in metres for height-anomaly baseline "
                             "(default 30). Larger = smoother reference surface.")
    parser.add_argument("--ha-threshold", type=float, default=1.5,
                        help="Height above local average (metres) to flag as canopy "
                             "(default 1.5). Lower = more sensitive.")
    parser.add_argument("--no-height-anomaly", action="store_true",
                        help="Disable height-anomaly detection (colour signal only).")
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

    colour_mask = (index >= args.threshold).astype(bool)
    console.print(f"[cyan]Colour mask ({index_name} >= {args.threshold}):[/cyan] "
                  f"{colour_mask.mean()*100:.1f}%")

    # --- height-anomaly detection ---
    ha_mask = np.zeros_like(colour_mask, dtype=bool)
    if not args.no_height_anomaly:
        dem_path = args.prep_dir / "dem.tif"
        if not dem_path.exists():
            console.print(f"[yellow]Height anomaly skipped:[/yellow] {dem_path} not found")
        else:
            from scipy.ndimage import gaussian_filter
            import rasterio as _rio
            with _rio.open(dem_path) as _src:
                dem = _src.read(1).astype("float32")
                dem_res = _src.res[0]  # metres/pixel
            sigma_px = args.ha_sigma / dem_res
            dem_smooth = gaussian_filter(dem, sigma=sigma_px)
            anomaly = dem - dem_smooth
            ha_mask_dem = anomaly >= args.ha_threshold
            # Resize ha_mask from DEM resolution to ortho resolution
            ha_img = Image.fromarray(ha_mask_dem.astype("uint8") * 255, mode="L")
            ha_img = ha_img.resize((out_w, out_h), Image.NEAREST)
            ha_mask = np.array(ha_img) > 127
            console.print(
                f"[cyan]Height anomaly (>{args.ha_threshold}m above {args.ha_sigma}m smooth):[/cyan] "
                f"{ha_mask_dem.mean()*100:.1f}% (DEM res)  "
                f"{ha_mask.mean()*100:.1f}% (ortho res)")

    # Resize colour mask to ortho resolution, then OR with height-anomaly mask
    colour_img = Image.fromarray(colour_mask.astype("uint8") * 255, mode="L")
    colour_img_out = colour_img.resize((out_w, out_h), Image.NEAREST)
    colour_mask_out = np.array(colour_img_out) > 127
    mask = (colour_mask_out | ha_mask).astype("uint8")
    console.print(f"[cyan]Combined (colour OR height):[/cyan] {mask.mean()*100:.1f}%")

    if args.dilate > 0:
        from scipy.ndimage import binary_dilation
        struct = np.ones((args.dilate * 2 + 1, args.dilate * 2 + 1), dtype=bool)
        mask = binary_dilation(mask.astype(bool), structure=struct).astype("uint8")
        console.print(f"[cyan]After dilation ({args.dilate}px):[/cyan] "
                      f"{mask.mean()*100:.1f}% vegetation")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask * 255, mode="L").save(out_path)
    console.print(f"[green]wrote[/green] {out_path}  ({out_w}x{out_h} px, {mask.mean()*100:.1f}% white)")
    console.print(
        "\nEdit in GIMP/Photoshop: [white]=smooth here[/white], [black]=keep as-is"
        "\nThen run: [cyan]uv run tools/smooth_dem.py[/cyan]")


if __name__ == "__main__":
    main()
