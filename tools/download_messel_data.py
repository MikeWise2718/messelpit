"""Open the Hessen Geodaten-online shop in a browser for the Messel Pit bbox.

The HVBG Intershop is the only canonical distribution channel for DGM1 + DOP20
and uses session-based orders, so we don't try to script the download itself.
This script just points you at the right shop URLs, prints the bbox, and lays
out the expected directory structure.
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich_argparse import RichHelpFormatter

# Coverage bbox (current build, ETRS89 / UTM 32N — EPSG:25832).
# The exact tile list is in data/tile_manifest.txt.
BBOX_EAST_MIN = 480_000
BBOX_EAST_MAX = 486_000
BBOX_NORTH_MIN = 5_526_000
BBOX_NORTH_MAX = 5_535_000
EXPECTED_TILES = 29

DGM1_URL = (
    "https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/"
    "ViewDownloadcenter-Start?path=3D-Daten/Digitales+Gel%C3%A4ndemodell+(DGM1)"
)
DOP20_URL = (
    "https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/"
    "ViewDownloadcenter-Start?path=Luftbildinformationen/Digitale+Orthophotos+DOP20"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="download_messel_data",
        description=__doc__,
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "-o", "--open-browser", action="store_true",
        help="Open the Hessen download-center pages in your default browser.",
    )
    parser.add_argument(
        "-d", "--data-dir", type=Path, default=Path("data/raw"),
        help="Where to place the unzipped tiles (default: data/raw).",
    )
    args = parser.parse_args()

    console = Console()

    bbox = Table(title="Messel Pit area of interest", show_header=False)
    bbox.add_column(style="cyan")
    bbox.add_column(style="white")
    bbox.add_row("CRS", "ETRS89 / UTM 32N (EPSG:25832)")
    bbox.add_row("Easting",  f"{BBOX_EAST_MIN:,} .. {BBOX_EAST_MAX:,}  "
                             f"({(BBOX_EAST_MAX-BBOX_EAST_MIN)//1000} km)")
    bbox.add_row("Northing", f"{BBOX_NORTH_MIN:,} .. {BBOX_NORTH_MAX:,}  "
                             f"({(BBOX_NORTH_MAX-BBOX_NORTH_MIN)//1000} km)")
    bbox.add_row("Tiles",    f"{EXPECTED_TILES} of each (1 km × 1 km grid, irregular footprint — "
                             "see data/tile_manifest.txt)")
    console.print(bbox)

    dgm1_dir = args.data_dir / "dgm1"
    dop20_dir = args.data_dir / "dop20"
    dgm1_dir.mkdir(parents=True, exist_ok=True)
    dop20_dir.mkdir(parents=True, exist_ok=True)

    instructions = Panel.fit(
        "[bold]1.[/bold] Open both shop pages (use [yellow]--open-browser[/yellow]).\n"
        "[bold]2.[/bold] Drill down: [cyan]Landkreis Darmstadt-Dieburg → "
        "Gemeinde Messel[/cyan]\n"
        "    plus [cyan]Stadt Darmstadt[/cyan] (the bbox crosses the city boundary).\n"
        "[bold]3.[/bold] Select the tiles listed in [green]data/tile_manifest.txt[/green].\n"
        "    Add them to your basket, accept the\n"
        "    [dim]Datenlizenz Deutschland – Zero – 2.0[/dim] terms,\n"
        "    and place the free order (no login required since 2022).\n"
        "[bold]4.[/bold] Download the resulting ZIPs.\n"
        f"[bold]5.[/bold] Unzip DGM1 tiles into [green]{dgm1_dir}[/green]\n"
        f"    and DOP20 tiles into [green]{dop20_dir}[/green].\n"
        "[bold]6.[/bold] Run [cyan]python tools/prep_rasters.py[/cyan].",
        title="One-time manual download",
        border_style="blue",
    )
    console.print(instructions)

    console.print(f"\n[cyan]DGM1  shop:[/cyan] {DGM1_URL}")
    console.print(f"[cyan]DOP20 shop:[/cyan] {DOP20_URL}\n")

    if args.open_browser:
        webbrowser.open(DGM1_URL)
        webbrowser.open(DOP20_URL)
        console.print("[green]Opened both shop pages in your browser.[/green]")


if __name__ == "__main__":
    main()
