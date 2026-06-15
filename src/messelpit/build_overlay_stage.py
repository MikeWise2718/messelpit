"""Author a wrapper USD stage that composes the OSM overlay onto the terrain.

The base terrain (``messel_lo.usd``) and the OSM overlay (``messel_osm.usd``,
produced by the sibling ``osm2usd`` builder) are kept as **separate, pristine
files**. This script authors a thin third stage that references both, so:

  out/messel_lo_with_osm.usd
    ├── (reference) messel_lo.usd     -> /World/Terrain   (untouched base)
    └── (reference) messel_osm.usd    -> /World/OSM        (toggleable overlay)

Neither input file is modified. ``build_usd.py`` can re-run and clobber
``messel_lo.usd`` freely without knowing OSM exists; re-run this script
afterwards to refresh the wrapper. The USD viewer points at the wrapper.

Both inputs share the same frame (Z-up, meters, SW-corner origin), so no
transform is needed on either reference -- they drop straight on top of each
other. ``osm2usd`` already projected + draped the overlay into that frame.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom
from rich.console import Console
from rich.table import Table
from rich_argparse import RichHelpFormatter

from messelpit import __version__


def author_wrapper(
    out_path: Path,
    layer_rels: list[str],
    console: Console,
) -> None:
    """Create ``out_path`` referencing the terrain + any overlay stages.

    ``layer_rels`` is an ordered list of paths (relative to the wrapper's own
    directory) to compose onto a single ``/World`` Xform: the terrain first,
    then any of the OSM / CAD / maps overlays. Each source's defaultPrim is
    ``/World`` (with its own subtree beneath -- ``/World/Terrain``,
    ``/World/OSM``, ``/World/CAD``, ...), so referencing them all onto one
    ``/World`` merges the subtrees under one world. All share the same
    Z-up/metres/SW-corner frame, so no transform is needed on any reference.

    Paths are relative so the bundle stays portable (everything lives in
    ``out/``).
    """
    stage = Usd.Stage.CreateNew(str(out_path))
    stage.SetMetadata("metersPerUnit", 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    world.GetPrim().SetCustomDataByKey("messelpit:wrapper_version", __version__)

    refs = world.GetPrim().GetReferences()
    for rel in layer_rels:
        refs.AddReference(rel)

    stage.GetRootLayer().Save()
    console.print(f"[green]wrote[/green] {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="build_overlay_stage",
        description=__doc__,
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "-t", "--terrain", type=Path, default=Path("out/messel_lo.usd"),
        help="Base terrain USD to reference (default out/messel_lo.usd).",
    )
    parser.add_argument(
        "-l", "--overlay", type=Path, default=None,
        help="OSM overlay USD from osm2usd (e.g. out/messel_osm.usd).",
    )
    parser.add_argument(
        "-c", "--cad", type=Path, default=None,
        help="Legacy CAD survey overlay USD (e.g. out/messel_cad.usd).",
    )
    parser.add_argument(
        "-m", "--maps", type=Path, default=None,
        help="Draped map overlay USD (e.g. out/messel_maps.usd).",
    )
    parser.add_argument(
        "-o", "--out", type=Path, default=Path("out/messel_lo_with_overlays.usd"),
        help="Wrapper stage to write (default out/messel_lo_with_overlays.usd).",
    )
    args = parser.parse_args()

    console = Console()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Terrain is required; overlays are opt-in. Order matters only for
    # determinism -- terrain first, then overlays in a fixed order.
    layers: list[tuple[str, Path]] = [("Terrain", args.terrain)]
    if args.overlay is not None:
        layers.append(("OSM overlay", args.overlay))
    if args.cad is not None:
        layers.append(("CAD overlay", args.cad))
    if args.maps is not None:
        layers.append(("Maps overlay", args.maps))

    if len(layers) == 1:
        raise SystemExit(
            "No overlay given. Pass at least one of --overlay/--cad/--maps "
            "(terrain alone needs no wrapper)."
        )

    for label, p in layers:
        if not p.exists():
            raise FileNotFoundError(
                f"Missing {label}: {p}. Build it first (terrain: "
                f"tools/build_variants.ps1; OSM: tools/build_osm_overlay.ps1; "
                f"CAD: messelpit.build_cad_overlay)."
            )

    # Reference paths relative to the wrapper's directory so out/ is portable.
    out_dir = args.out.parent.resolve()
    rels = [
        (label, "./" + str(p.resolve().relative_to(out_dir)).replace("\\", "/"))
        for label, p in layers
    ]

    author_wrapper(args.out, [rel for _, rel in rels], console)

    summary = Table(title="Overlay wrapper", show_header=False)
    summary.add_column(style="cyan")
    summary.add_column()
    summary.add_row("Wrapper", str(args.out))
    for label, rel in rels:
        summary.add_row(f"{label} ref", rel)
    summary.add_row("Up axis", "Z")
    summary.add_row("Units", "meters")
    console.print(summary)


if __name__ == "__main__":
    main()
