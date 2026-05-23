"""Combine an auto-generated and a hand-painted vegetation mask.

The auto-generated mask (make_veg_mask.py) catches well-lit, high-greenness
canopy. The hand-painted mask fills in trees that are spectrally ambiguous
(shadowed, low-greenness species, mixed pixels). This script merges both with
a logical OR so smooth_dem.py can use the union.

As a learning step, it also checks whether any pixels missed by the auto-mask
sit at a higher greenness than its current threshold — if they do, it lowers
the threshold to capture them before ORing. If they don't (median greenness of
missed pixels is below the original threshold), the auto-mask threshold is left
alone, and the hand-painted mask is the sole source for those areas.

Outputs:
  vegetation_troubleshooting/veg_mask_combined.png

Run smooth_dem.py afterwards:
  uv run tools/smooth_dem.py -m vegetation_troubleshooting/veg_mask_combined.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from rich.console import Console
from rich_argparse import RichHelpFormatter

DEFAULT_AUTO_THRESHOLD = 0.15  # matches make_veg_mask.py default


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="combine_veg_masks", description=__doc__,
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "--ortho", type=Path, default=Path("data/prep/ortho.png"),
        help="Colour orthophoto used to compute greenness index (default: data/prep/ortho.png)")
    parser.add_argument(
        "--hp", type=Path,
        default=Path("vegetation_troubleshooting/veg_mask_hp.png"),
        help="Hand-painted mask (white = vegetation)")
    parser.add_argument(
        "--auto", type=Path,
        default=Path("vegetation_troubleshooting/veg_mask.png"),
        help="Auto-generated mask to combine with the hand-painted one")
    parser.add_argument(
        "-o", "--out", type=Path,
        default=Path("vegetation_troubleshooting/veg_mask_combined.png"))
    parser.add_argument(
        "--auto-threshold", type=float, default=DEFAULT_AUTO_THRESHOLD,
        help=f"Greenness threshold used by make_veg_mask.py (default {DEFAULT_AUTO_THRESHOLD}). "
             "Used as the reference when checking whether missed pixels can be captured.")
    parser.add_argument(
        "--dilate", type=int, default=3,
        help="Dilation radius in pixels applied to any improved auto-mask (default 3).")
    args = parser.parse_args()

    console = Console()

    for p, name in [(args.ortho, "ortho"), (args.hp, "hand-painted mask")]:
        if not p.exists():
            console.print(f"[red]{p} not found[/red] — {name} is required")
            raise SystemExit(1)

    # --- load and resize everything to the same dims (ortho is the reference) ---
    console.print(f"[cyan]Loading ortho:[/cyan] {args.ortho}")
    ortho = np.array(Image.open(args.ortho).convert("RGB"), dtype="float32")
    W, H = ortho.shape[1], ortho.shape[0]
    r, g = ortho[:, :, 0], ortho[:, :, 1]
    greenness = (g - r) / (g + r + 1e-6)
    console.print(f"  {W}x{H} px  greenness {greenness.min():.3f}..{greenness.max():.3f}")

    def load_mask(path: Path) -> np.ndarray:
        img = Image.open(path).convert("L")
        if img.size != (W, H):
            console.print(f"  resizing {img.size} -> ({W}, {H})")
            img = img.resize((W, H), Image.NEAREST)
        return np.array(img) > 127

    console.print(f"[cyan]Loading hand-painted mask:[/cyan] {args.hp}")
    hp = load_mask(args.hp)
    console.print(f"  coverage: {hp.mean()*100:.2f}%  ({hp.sum():,} px)")

    if args.auto.exists():
        console.print(f"[cyan]Loading auto-generated mask:[/cyan] {args.auto}")
        auto = load_mask(args.auto)
        console.print(f"  coverage: {auto.mean()*100:.2f}%  ({auto.sum():,} px)")
    else:
        console.print(f"[yellow]{args.auto} not found — using blank auto-mask[/yellow]")
        auto = np.zeros((H, W), dtype=bool)

    # --- check whether missed pixels are above the auto threshold ---
    missed = hp & ~auto
    n_missed = missed.sum()
    console.print(f"\n[cyan]Hand-painted pixels missed by auto-mask:[/cyan] "
                  f"{n_missed:,} ({n_missed*100/max(hp.sum(),1):.1f}% of hand-painted)")

    improved_auto = auto.copy()
    if n_missed > 100:
        missed_greenness = greenness[missed]
        missed_median = float(np.median(missed_greenness))
        console.print(
            f"  greenness at missed pixels: "
            f"min={missed_greenness.min():.3f}  "
            f"mean={missed_greenness.mean():.3f}  "
            f"median={missed_median:.3f}  "
            f"max={missed_greenness.max():.3f}")

        if missed_median >= args.auto_threshold:
            # Missed pixels are above the threshold — the auto-mask should have caught them
            # but didn't (possibly missed due to mosaic gaps or dilation). Lower threshold.
            new_threshold = missed_median * 0.9
            improved_auto = (greenness >= new_threshold).astype(bool)
            if args.dilate > 0:
                from scipy.ndimage import binary_dilation
                struct = np.ones((args.dilate * 2 + 1, args.dilate * 2 + 1), dtype=bool)
                improved_auto = binary_dilation(improved_auto, structure=struct)
            console.print(
                f"  [green]Missed pixels are above threshold ({missed_median:.3f} >= "
                f"{args.auto_threshold:.3f}) — lowering auto threshold to {new_threshold:.3f}[/green]")
            console.print(f"  Improved auto coverage: {improved_auto.mean()*100:.2f}%")
        else:
            console.print(
                f"  [yellow]Missed pixels sit BELOW the auto threshold "
                f"(median {missed_median:.3f} < {args.auto_threshold:.3f}) — "
                f"spectrally indistinguishable from non-vegetation.\n"
                f"  Keeping original auto-mask; hand-painted pixels cover those areas.[/yellow]")

    # --- combine ---
    combined = np.logical_or(improved_auto, hp)
    console.print(f"\n[cyan]Combined mask coverage:[/cyan] "
                  f"{combined.mean()*100:.2f}%  ({combined.sum():,} px)")

    out_img = Image.fromarray((combined * 255).astype("uint8"), mode="L")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(args.out)
    console.print(f"[green]wrote[/green] {args.out}  ({W}x{H} px)")
    console.print(f"\nNext: [cyan]uv run tools/smooth_dem.py -m {args.out}[/cyan]")


if __name__ == "__main__":
    main()
