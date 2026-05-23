"""Interpolate DEM elevations under a vegetation mask.

Reads data/prep/dem.tif and data/prep/veg_mask.png.
White pixels in the mask are treated as unknown (canopy hits);
their elevations are replaced by smooth interpolation from surrounding
bare-ground pixels. Output is data/prep/dem_smooth.tif.

Run make_veg_mask.py first, edit the mask in GIMP if needed, then run this.
build_usd.py will use dem_smooth.tif automatically if it exists.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from scipy.ndimage import distance_transform_edt
from rich.console import Console
from rich_argparse import RichHelpFormatter


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="smooth_dem", description=__doc__,
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("-d", "--dem", type=Path, default=Path("data/prep/dem.tif"))
    parser.add_argument("-m", "--mask", type=Path,
                        default=Path("vegetation_troubleshooting/veg_mask.png"))
    parser.add_argument("-o", "--out", type=Path,
                        default=Path("vegetation_troubleshooting/dem_smooth.tif"))
    parser.add_argument("--blur", type=float, default=0.0,
                        help="Optional Gaussian blur sigma (metres) applied after "
                             "interpolation to further smooth the filled area (default 0 = off).")
    parser.add_argument("--feather", type=float, default=30.0,
                        help="Width in metres over which the filled DEM is blended back "
                             "into the original at mask edges (default 10). "
                             "Eliminates jagged boundary artefacts. Set 0 to disable.")
    args = parser.parse_args()

    console = Console()

    if not args.dem.exists():
        console.print(f"[red]{args.dem} not found[/red] — run prep_rasters.py first")
        raise SystemExit(1)
    if not args.mask.exists():
        console.print(f"[red]{args.mask} not found[/red] — run make_veg_mask.py first")
        raise SystemExit(1)

    with rasterio.open(args.dem) as src:
        dem = src.read(1).astype("float32")
        profile = src.profile.copy()

    console.print(f"[cyan]DEM:[/cyan] {dem.shape[1]}x{dem.shape[0]} px")

    mask_img = Image.open(args.mask).convert("L")
    if mask_img.size != (dem.shape[1], dem.shape[0]):
        console.print(
            f"[yellow]Resizing mask[/yellow] {mask_img.size} -> "
            f"({dem.shape[1]}, {dem.shape[0]})")
        mask_img = mask_img.resize((dem.shape[1], dem.shape[0]), Image.NEAREST)

    veg = np.array(mask_img) > 127   # True = smooth here
    n_veg = int(veg.sum())
    console.print(f"[cyan]Masked pixels:[/cyan] {n_veg:,} ({n_veg*100/veg.size:.1f}%)")

    if n_veg == 0:
        console.print("[yellow]Mask is empty — nothing to smooth. Copying DEM as-is.[/yellow]")
        smooth = dem.copy()
    else:
        from scipy.ndimage import gaussian_filter

        # Gaussian-blur the entire DEM — this suppresses tree-bump spikes while
        # preserving large-scale terrain shape (valleys, ridges). No fill needed:
        # masked pixels already have elevation values, they just need smoothing.
        blur_sigma = args.blur if args.blur > 0 else 30.0
        dem_blurred = gaussian_filter(dem, sigma=blur_sigma)
        console.print(f"[cyan]DEM blur:[/cyan] Gaussian sigma={blur_sigma} m")

        # Soft mask: Gaussian-blur the binary mask to create a 0..1 blend weight.
        # This feathers the transition so there is no hard edge between smoothed
        # and original terrain.
        feather_sigma = args.feather if args.feather > 0 else 30.0
        soft_mask = gaussian_filter(veg.astype("float32"), sigma=feather_sigma)
        console.print(f"[cyan]Feather:[/cyan] Gaussian blend, sigma={feather_sigma} m")

        # Blend: outside mask → original DEM; inside mask → blurred DEM; smooth transition.
        smooth = dem * (1.0 - soft_mask) + dem_blurred * soft_mask

    profile.update(dtype="float32", compress="lzw", tiled=True,
                   blockxsize=256, blockysize=256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.out, "w", **profile) as dst:
        dst.write(smooth, 1)

    orig_range = f"{dem.min():.1f}..{dem.max():.1f}"
    new_range = f"{smooth.min():.1f}..{smooth.max():.1f}"
    console.print(f"[green]wrote[/green] {args.out}")
    console.print(f"  elevation range: {orig_range} -> {new_range} m")
    console.print("\nNext: [cyan]uv run src/messelpit/build_usd.py[/cyan]  "
                  "(will use dem_smooth.tif automatically)")


if __name__ == "__main__":
    main()
