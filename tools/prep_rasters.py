"""Mosaic, crop, and recenter the Hessen DGM1 + DOP20 tiles for the Messel Pit.

Inputs:
  data/raw/dgm1/*.tif         1 m DEM tiles (EPSG:25832, float32)
  data/raw/dop20/*.jpg|*.tif  0.2 m RGB(I) orthophoto tiles (EPSG:25832, .jgw world file)

The bbox is taken from the union of the DGM1 tiles; the DOP20 mosaic is cropped to
that same bbox. Outputs use local meters with origin at the SW corner.

Outputs:
  data/prep/dem.tif       NxN float32 (1 m/px)
  data/prep/ortho.png     MxM RGB     (--ortho-res m/px, default 0.5)
  data/prep/origin.json   original UTM origin + DEM stats
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from scipy.ndimage import distance_transform_edt
from rasterio.crs import CRS
from rasterio.merge import merge
from rasterio.transform import from_origin
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich_argparse import RichHelpFormatter

HESSEN_CRS = CRS.from_epsg(25832)
DEM_RES = 1.0
TILE_NAME_RE = re.compile(r"_32_(\d{3,4})_(\d{4,5})_")


def _list_tiles(tile_dir: Path, suffixes: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for s in suffixes:
        out.extend(tile_dir.glob(f"*{s}"))
    return sorted(out)


def _bbox_from_tile_names(tiles: list[Path]) -> tuple[float, float, float, float]:
    """Return (xmin, ymin, xmax, ymax) in EPSG:25832 from filename grid coords.
    Hessen names a 1km tile by its SW corner in km: dgm1_32_<E_km>_<N_km>_1_he.tif"""
    coords = []
    for t in tiles:
        m = TILE_NAME_RE.search(t.name)
        if not m:
            continue
        e_km = int(m.group(1))
        n_km = int(m.group(2))
        coords.append((e_km * 1000, n_km * 1000))
    if not coords:
        raise ValueError("No tile coords parseable from filenames")
    es = [c[0] for c in coords]
    ns = [c[1] for c in coords]
    return (min(es), min(ns), max(es) + 1000, max(ns) + 1000)


def _open_with_crs(path: Path):
    """Open a tile, forcing EPSG:25832 if the file lacks one (DOP20 JPEG case).

    WarpedVRT with src_crs == crs is a no-op resample-wise but lets us attach
    a CRS to the dataset without rewriting the underlying JPEG bytes.
    """
    from rasterio.vrt import WarpedVRT
    src = rasterio.open(path)
    if src.crs is None:
        return WarpedVRT(src, src_crs=HESSEN_CRS, crs=HESSEN_CRS)
    return src


def _mosaic(tile_dir: Path, suffixes: tuple[str, ...], bbox, console: Console, label: str):
    tiles = _list_tiles(tile_dir, suffixes)
    if not tiles:
        raise FileNotFoundError(f"No tiles in {tile_dir} (looked for {suffixes})")
    console.print(f"[cyan]{label}:[/cyan] opening {len(tiles)} tiles")
    sources = [_open_with_crs(t) for t in tiles]
    mosaic, transform = merge(sources, bounds=bbox)
    profile = sources[0].profile
    for s in sources:
        s.close()
    return mosaic, transform, profile


def prep_dem(raw_dir: Path, out_dir: Path, bbox, console: Console) -> dict:
    mosaic, transform, profile = _mosaic(
        raw_dir / "dgm1", (".tif", ".tiff"), bbox, console, "DGM1")
    band = mosaic[0]

    # Hessen DGM1 ships without a nodata tag; cells outside the Gemeinde are 0.
    # Anything outside a plausible Hessen elevation range is treated as NoData,
    # then filled via nearest-neighbour from the valid region.
    invalid = (band <= 0) | (band > 1000) | ~np.isfinite(band)
    n_invalid = int(invalid.sum())
    if n_invalid:
        console.print(f"[yellow]filling[/yellow] {n_invalid:,} no-data pixels "
                      f"({n_invalid * 100 / band.size:.1f}%) via nearest neighbour")
        _, (iy, ix) = distance_transform_edt(invalid, return_indices=True)
        band = band[iy, ix]

    valid = band[~invalid] if n_invalid < band.size else band
    stats = {
        "min": float(valid.min()), "max": float(valid.max()),
        "mean": float(valid.mean()), "shape": list(band.shape),
        "filled_pixels": n_invalid,
    }

    width_m = bbox[2] - bbox[0]
    height_m = bbox[3] - bbox[1]
    local_transform = from_origin(0.0, height_m, DEM_RES, DEM_RES)
    out_profile = profile.copy()
    out_profile.pop("blockxsize", None)
    out_profile.pop("blockysize", None)
    out_profile.update(
        driver="GTiff", height=band.shape[0], width=band.shape[1],
        transform=local_transform, crs=None,
        compress="lzw", tiled=True, dtype="float32",
        blockxsize=256, blockysize=256,
    )
    dem_path = out_dir / "dem.tif"
    with rasterio.open(dem_path, "w", **out_profile) as dst:
        dst.write(band.astype("float32"), 1)
    console.print(
        f"[green]wrote[/green] {dem_path}  ({band.shape[1]}x{band.shape[0]}, "
        f"z=[{stats['min']:.1f}, {stats['max']:.1f}] m)")
    return stats


def prep_ortho(raw_dir: Path, out_dir: Path, bbox, ortho_res_m: float,
               max_tex_dim: int, console: Console) -> tuple[int, int]:
    mosaic, _, profile = _mosaic(
        raw_dir / "dop20", (".jpg", ".jpeg", ".tif", ".tiff"),
        bbox, console, "DOP20")
    bands = mosaic.shape[0]
    if bands < 3:
        raise ValueError(f"Expected >=3 bands in DOP20 tiles, got {bands}")
    rgb = mosaic[:3]
    arr = np.transpose(rgb, (1, 2, 0)).astype("uint8")

    # Replace black border pixels (all-zero RGB, from outside-coverage areas)
    # with a neutral mid-grey so the texture doesn't show stark edges.
    black = (arr.sum(axis=-1) == 0)
    if black.any():
        arr[black] = (110, 115, 100)  # muted greenish grey
        console.print(f"[yellow]filled[/yellow] {int(black.sum()):,} "
                      f"black border pixels in ortho ({black.mean()*100:.1f}%)")

    width_m = bbox[2] - bbox[0]
    height_m = bbox[3] - bbox[1]
    target_w = int(width_m / ortho_res_m)
    target_h = int(height_m / ortho_res_m)

    # D3D12 (Omniverse RTX on Windows) caps Texture2D at 16384 per axis. usdview's
    # OpenGL Storm renderer happily takes 32k+ so unconstrained output looks fine
    # there but fails to upload in Kit. Scale both axes proportionally so the long
    # axis fits under the cap.
    long_dim = max(target_w, target_h)
    if long_dim > max_tex_dim:
        scale = max_tex_dim / long_dim
        new_w = int(target_w * scale)
        new_h = int(target_h * scale)
        effective_res = ortho_res_m * long_dim / max_tex_dim
        console.print(
            f"[yellow]capping[/yellow] ortho at max_tex_dim={max_tex_dim}: "
            f"{target_w}x{target_h} -> {new_w}x{new_h} "
            f"(effective res {effective_res:.2f} m/px)")
        target_w, target_h = new_w, new_h

    img = Image.fromarray(arr, mode="RGB").resize((target_w, target_h), Image.BILINEAR)
    ortho_path = out_dir / "ortho.png"
    img.save(ortho_path, optimize=True)
    console.print(f"[green]wrote[/green] {ortho_path}  ({target_w}x{target_h}, RGB)")
    return target_w, target_h


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="prep_rasters", description=__doc__,
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("-i", "--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("-o", "--out-dir", type=Path, default=Path("data/prep"))
    parser.add_argument("--ortho-res", type=float, default=0.5,
                        help="Orthophoto resampling resolution in m/px (default 0.5).")
    parser.add_argument("--max-tex-dim", "-mt", type=int, default=16384,
                        help="Max texture dimension in px on the long axis "
                             "(default 16384, the D3D12/Omniverse RTX cap). "
                             "Ortho is scaled down proportionally if exceeded.")
    parser.add_argument("--skip-ortho", action="store_true",
                        help="Only build the DEM (faster while iterating).")
    parser.add_argument("--bbox", type=float, nargs=4,
                        metavar=("XMIN", "YMIN", "XMAX", "YMAX"),
                        help="Crop to this UTM 32N bbox in metres instead of the "
                             "full tile extent. Example: --bbox 481700 5528100 483000 5529800")
    parser.add_argument("--pit", action="store_true",
                        help="Shortcut: crop to Messel Pit + 300 m buffer "
                             "(481700 5528100 483000 5529800).")
    args = parser.parse_args()

    console = Console()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    dgm1_tiles = _list_tiles(args.raw_dir / "dgm1", (".tif", ".tiff"))
    if not dgm1_tiles:
        raise FileNotFoundError(f"No DGM1 tiles in {args.raw_dir / 'dgm1'}")

    if args.pit:
        bbox = (481_700, 5_528_100, 483_000, 5_529_800)
    elif args.bbox:
        bbox = tuple(args.bbox)
    else:
        bbox = _bbox_from_tile_names(dgm1_tiles)
    console.print(
        f"[cyan]Mosaic bbox (UTM 32N):[/cyan] "
        f"{bbox[0]:,}..{bbox[2]:,} E  x  {bbox[1]:,}..{bbox[3]:,} N  "
        f"= {bbox[2]-bbox[0]:,} x {bbox[3]-bbox[1]:,} m")

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t = p.add_task("Building DEM mosaic...", total=None)
        stats = prep_dem(args.raw_dir, args.out_dir, bbox, console)
        p.remove_task(t)
        ortho_dims = None
        if not args.skip_ortho:
            t = p.add_task("Building orthophoto mosaic...", total=None)
            ortho_dims = prep_ortho(args.raw_dir, args.out_dir, bbox,
                                    args.ortho_res, args.max_tex_dim, console)
            p.remove_task(t)
            veg_dir = Path("vegetation_troubleshooting")
            if veg_dir.exists():
                import shutil
                shutil.copy2(args.out_dir / "ortho.png", veg_dir / "ortho.png")
                console.print(f"[cyan]copied[/cyan] ortho.png -> {veg_dir / 'ortho.png'}")

    origin = {
        "utm_zone": "32N", "epsg": 25832,
        "utm_sw_easting": bbox[0], "utm_sw_northing": bbox[1],
        "width_m": bbox[2] - bbox[0], "height_m": bbox[3] - bbox[1],
        "dem_resolution_m": DEM_RES,
        "ortho_resolution_m": args.ortho_res if not args.skip_ortho else None,
        "ortho_dims_px": list(ortho_dims) if ortho_dims else None,
        "dem_stats": stats,
    }
    (args.out_dir / "origin.json").write_text(json.dumps(origin, indent=2))

    summary = Table(title="Prep summary", show_header=False)
    summary.add_column(style="cyan"); summary.add_column()
    summary.add_row("DEM",         str(args.out_dir / "dem.tif"))
    if ortho_dims:
        summary.add_row("Ortho",   str(args.out_dir / "ortho.png"))
    summary.add_row("Origin meta", str(args.out_dir / "origin.json"))
    summary.add_row("Elev range",  f"{stats['min']:.1f} .. {stats['max']:.1f} m "
                                   f"(span {stats['max']-stats['min']:.1f} m)")
    console.print(summary)
    console.print("\nNext: [cyan]python -m messelpit.build_usd[/cyan]")


if __name__ == "__main__":
    main()
