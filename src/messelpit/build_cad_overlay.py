"""Author a USD overlay from the legacy 2010-survey CAD (MESSEL.DXF et al.).

Reads an AutoCAD R12 DXF (the contour + situation survey of Grube Messel
in ``D:\\senckenberg\\messel_karten``) and authors a pristine overlay
stage whose contents hang under ``/World/CAD/<group>``. A thin wrapper
(``build_overlay_stage.py``) references this onto the terrain; the USD
viewer toggles the groups via a sidecar "Survey" tab.

This is the messelpit side of the cad-overlay feature -- it owns *all*
geo + USD authoring (coordinate transform, curve/point/material
authoring). The viewer never authors geometry; see
``specs/legacy-cad-and-map-overlays.md`` for the responsibility split.

Coordinate frame
----------------
The DXF is UTM 32N (EPSG:25832) with the leading "5" dropped from the
northing -- the *same* datum/projection as the LiDAR terrain, so there is
**no reprojection**, only a translation into the scene's SW-corner local
frame::

    local_x = E_dxf               - utm_sw_easting     (480000)
    local_y = (N_dxf + 5_000_000) - utm_sw_northing    (5526000)
    local_z = Z_dxf                                     (meters MSL, as-is)

Origin constants come from ``data/prep/origin.json`` (the same source of
truth the terrain + OSM use). After transform we assert the kept geometry
lands inside the DEM bbox (0..width x 0..height) and bail loudly if not.

What we keep
------------
The DXF carries a lot of cartographic clutter (hatching, frame, pattern
classes) and a sprinkling of garbage vertices with absurd coordinates.
We keep only what reads as real survey content:

* **Contours** -- ``HL_0$25 / HL_0$5 / HL_1$0 / HL_5$0`` POLYLINEs (the
  ``$`` is R12's escaped ``.`` -> 0.25 / 0.5 / 1.0 / 5.0 m intervals).
  Each polyline is flat at its contour elevation. -> BasisCurves, grouped
  by interval under ``/World/CAD/Survey/Contours/{c025,c05,c10,c50}``.
* **Spot heights** -- ``KOTE1`` INSERTs (528 of them, all clean) carry the
  surveyed elevation in their insertion Z. -> UsdGeom.Points under
  ``/World/CAD/Survey/SpotHeights``.
* **Facilities** -- the ``ANLAGEN`` layer (a few polylines/circles).
  -> BasisCurves under ``/World/CAD/Survey/Facilities``.

TEXTE labels, flow arrows, and the second DXF (dgm_messel.dxf) are later
phases; see the spec.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import ezdxf
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt
from rich.console import Console
from rich.table import Table
from rich_argparse import RichHelpFormatter

from messelpit import __version__

# Northing reconstruction. The DXF northings are truncated (5_5xx_xxx printed
# as 5xx_xxx), but it is NOT a clean "+5_000_000": that lands the geometry
# ~1.8 km too far north. The value below was derived by aligning the DXF
# pit-floor spot heights (lowest KOTE1 elevations) to the LiDAR DEM pit floor
# (cells below 122 m in data/prep/dem.tif). Easting needs no such fudge -- it
# is raw UTM 32N, so local_x = E_dxf - utm_sw_easting. Override with
# --northing-restore if a different DXF sheet uses another truncation.
NORTHING_RESTORE = 4_998_232

# Contour layer name -> (group prim leaf, interval metres) for the four
# Hoehenlinien classes. R12 escapes "." as "$".
CONTOUR_LAYERS = {
    "HL_0$25": ("c025", 0.25),
    "HL_0$5": ("c05", 0.5),
    "HL_1$0": ("c10", 1.0),
    "HL_5$0": ("c50", 5.0),
}

# Default ribbon width (world metres) per contour leaf. Independently
# tunable so the bold 5 m index lines don't drown the fine intervals --
# override any of them with --width-cNN on the CLI. Facilities reuse c10.
DEFAULT_CONTOUR_WIDTHS = {
    "c025": 1.5,
    "c05": 2.0,
    "c10": 2.5,
    "c50": 4.0,
}

# Spot-height + facility layers.
SPOT_BLOCK = "KOTE1"
FACILITY_LAYER = "ANLAGEN"

# Plausible elevation band (DEM is 103.8..228.0 m; allow margin). Used to
# drop garbage polylines/inserts with absurd Z. Vertices outside the DEM
# bbox (after transform) are dropped too.
Z_MIN, Z_MAX = 90.0, 240.0

# Per-group RGB colour (legible on the aerial ortho). Faint thin intervals,
# bold coarse ones; warm for spot heights; cyan for facilities.
GROUP_COLOR = {
    "c025": (0.55, 0.55, 0.60),
    "c05": (0.65, 0.65, 0.45),
    "c10": (0.85, 0.70, 0.30),
    "c50": (0.95, 0.45, 0.15),
    "SpotHeights": (1.0, 0.95, 0.30),
    "Facilities": (0.20, 0.85, 0.95),
}

CAD_ROOT = "/World/CAD/Survey"


def _transform(x: float, y: float, z: float, sw_e: float, sw_n: float,
               northing_restore: float):
    """DXF (truncated UTM) -> scene local frame (Z-up metres)."""
    return (x - sw_e, (y + northing_restore) - sw_n, z)


def _polyline_points(e):
    """Return the [(x,y,z), ...] vertices of a (LW)POLYLINE, or None."""
    if e.dxftype() == "POLYLINE":
        return [tuple(v.dxf.location) for v in e.vertices]
    if e.dxftype() == "LWPOLYLINE":
        z = e.dxf.elevation
        return [(p[0], p[1], z) for p in e.get_points()]
    return None


def _in_bbox(x: float, y: float, w: float, h: float, margin: float = 50.0) -> bool:
    return -margin <= x <= w + margin and -margin <= y <= h + margin


def collect_geometry(doc, sw_e: float, sw_n: float, width: float, height: float,
                     northing_restore: float, console: Console):
    """Walk the DXF modelspace, transform + filter, group by leaf name.

    Returns ``(contours, spots, facilities, stats)`` where ``contours`` is
    ``{leaf: [np.ndarray(N,3), ...]}``, ``spots`` is ``np.ndarray(M,3)``,
    ``facilities`` is ``[np.ndarray(N,3), ...]``.
    """
    msp = doc.modelspace()
    contours: dict[str, list] = {leaf: [] for leaf, _ in CONTOUR_LAYERS.values()}
    facilities: list = []
    spots: list = []
    dropped_z = 0
    dropped_bbox = 0

    for e in msp.query("POLYLINE LWPOLYLINE"):
        layer = e.dxf.layer
        target = None
        if layer in CONTOUR_LAYERS:
            target = contours[CONTOUR_LAYERS[layer][0]]
        elif layer == FACILITY_LAYER:
            target = facilities
        if target is None:
            continue
        pts = _polyline_points(e)
        if not pts or len(pts) < 2:
            continue
        zs = [p[2] for p in pts]
        # Flat-ish + plausible elevation (drops the absurd-Z garbage lines).
        if (max(zs) - min(zs)) > 1.0 or not (Z_MIN <= zs[0] <= Z_MAX):
            dropped_z += 1
            continue
        local = [_transform(x, y, z, sw_e, sw_n, northing_restore) for (x, y, z) in pts]
        if not all(_in_bbox(lx, ly, width, height) for (lx, ly, _) in local):
            dropped_bbox += 1
            continue
        target.append(np.asarray(local, dtype=np.float32))

    for e in msp.query("INSERT"):
        if e.dxf.name != SPOT_BLOCK:
            continue
        x, y, z = e.dxf.insert
        if not (Z_MIN <= z <= Z_MAX):
            dropped_z += 1
            continue
        lx, ly, lz = _transform(x, y, z, sw_e, sw_n, northing_restore)
        if not _in_bbox(lx, ly, width, height):
            dropped_bbox += 1
            continue
        spots.append((lx, ly, lz))

    spots = np.asarray(spots, dtype=np.float32) if spots else np.zeros((0, 3), np.float32)
    stats = {"dropped_z": dropped_z, "dropped_bbox": dropped_bbox}
    return contours, spots, facilities, stats


def _curve_material(stage, parent_path: str, color):
    """Author a UsdPreviewSurface (emissive so ribbons read on the ortho)."""
    mat = UsdShade.Material.Define(stage, f"{parent_path}/Mat")
    pbr = UsdShade.Shader.Define(stage, f"{parent_path}/Mat/PBR")
    pbr.CreateIdAttr("UsdPreviewSurface")
    c = Gf.Vec3f(*color)
    pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(c)
    pbr.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(c)
    pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    mat.CreateSurfaceOutput().ConnectToSource(pbr.ConnectableAPI(), "surface")
    return mat


def _ribbon_for_polyline(pl: np.ndarray, half_w: float, z_lift: float):
    """Build a flat horizontal ribbon mesh for one polyline.

    Each vertex is offset +/- ``half_w`` perpendicular to its (XY-projected)
    direction, producing a 2-vertex-wide strip. Returns
    ``(verts (2N,3), tri_indices (list[int]))`` with vertices ordered
    left0,right0,left1,right1,... The ribbon is lifted ``z_lift`` above the
    contour's own Z so it sits on top of the terrain mesh and doesn't z-fight.

    RTX renders meshes reliably (unlike linear BasisCurves, which it drops),
    so contours are authored as ribbons -- the same call the OSM builder
    made for roads.
    """
    n = len(pl)
    # Per-vertex 2D direction = average of incoming/outgoing segment dirs.
    d = np.zeros((n, 2), dtype=np.float64)
    seg = pl[1:, :2] - pl[:-1, :2]
    seg_len = np.linalg.norm(seg, axis=1, keepdims=True)
    seg_unit = np.divide(seg, seg_len, out=np.zeros_like(seg), where=seg_len > 1e-9)
    d[:-1] += seg_unit
    d[1:] += seg_unit
    dl = np.linalg.norm(d, axis=1, keepdims=True)
    d = np.divide(d, dl, out=np.tile([1.0, 0.0], (n, 1)), where=dl > 1e-9)
    # Perpendicular (left normal) in XY.
    perp = np.stack([-d[:, 1], d[:, 0]], axis=1)
    left = pl[:, :2] + perp * half_w
    right = pl[:, :2] - perp * half_w
    z = pl[:, 2:3] + z_lift
    vl = np.concatenate([left, z], axis=1)
    vr = np.concatenate([right, z], axis=1)
    # Interleave: [l0, r0, l1, r1, ...]
    verts = np.empty((2 * n, 3), dtype=np.float32)
    verts[0::2] = vl
    verts[1::2] = vr
    tris = []
    for i in range(n - 1):
        a, b, c, dd = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        tris += [a, b, dd, a, dd, c]  # two tris per quad, CCW-ish
    return verts, tris


def _author_ribbons(stage, prim_path: str, polylines: list, color,
                    width: float, z_lift: float):
    """Author one Mesh holding flat ribbons for every polyline in a group."""
    half_w = float(width) / 2.0
    all_verts = []
    fvi = []
    fvc = []
    base = 0
    for pl in polylines:
        if len(pl) < 2:
            continue
        verts, tris = _ribbon_for_polyline(pl, half_w, z_lift)
        all_verts.append(verts)
        fvi.extend(base + t for t in tris)
        fvc.extend([3] * (len(tris) // 3))
        base += len(verts)

    mesh = UsdGeom.Mesh.Define(stage, prim_path)
    pts = (np.concatenate(all_verts, axis=0) if all_verts
           else np.zeros((0, 3), np.float32))
    mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(pts))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(fvc))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(fvi))
    mesh.CreateSubdivisionSchemeAttr("none")
    mesh.CreateDoubleSidedAttr(True)
    if len(pts):
        mn = [float(v) for v in pts.min(axis=0)]
        mx = [float(v) for v in pts.max(axis=0)]
        mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*mn), Gf.Vec3f(*mx)]))
    mat = _curve_material(stage, prim_path, color)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
    return len(polylines), len(pts)


def _author_markers(stage, prim_path: str, pts: np.ndarray, color,
                   width: float, z_lift: float):
    """Author one Mesh of small flat square markers, one per spot height.

    Points get dropped by RTX just like BasisCurves, so spot heights are
    authored as little horizontal quads (a 4-vert square per point).
    """
    half = float(width) / 2.0
    quad = np.array([[-half, -half], [half, -half], [half, half], [-half, half]],
                    dtype=np.float32)
    all_verts = []
    fvi = []
    fvc = []
    for i, (x, y, z) in enumerate(pts):
        sq = np.concatenate([quad + [x, y], np.full((4, 1), z + z_lift, np.float32)],
                            axis=1)
        all_verts.append(sq)
        b = 4 * i
        fvi += [b, b + 1, b + 2, b, b + 2, b + 3]
        fvc += [3, 3]

    mesh = UsdGeom.Mesh.Define(stage, prim_path)
    verts = (np.concatenate(all_verts, axis=0) if all_verts
             else np.zeros((0, 3), np.float32))
    mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(verts))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(fvc))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(fvi))
    mesh.CreateSubdivisionSchemeAttr("none")
    mesh.CreateDoubleSidedAttr(True)
    if len(verts):
        mn = [float(v) for v in verts.min(axis=0)]
        mx = [float(v) for v in verts.max(axis=0)]
        mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*mn), Gf.Vec3f(*mx)]))
    mat = _curve_material(stage, prim_path, color)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
    return len(pts)


def author_stage(out_path: Path, contours: dict, spots: np.ndarray,
                 facilities: list, origin_meta: dict, console: Console,
                 contour_widths: dict, spot_width: float,
                 z_lift: float) -> dict:
    stage = Usd.Stage.CreateNew(str(out_path))
    stage.SetMetadata("metersPerUnit", 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))

    UsdGeom.Xform.Define(stage, "/World/CAD")
    survey = UsdGeom.Xform.Define(stage, CAD_ROOT)
    survey.GetPrim().SetCustomDataByKey("messelpit:cad_overlay_version", __version__)
    survey.GetPrim().SetCustomDataByKey("messelpit:source", "MESSEL.DXF")

    UsdGeom.Xform.Define(stage, f"{CAD_ROOT}/Contours")
    counts = {}
    for leaf, interval in sorted(CONTOUR_LAYERS.values(), key=lambda t: t[1]):
        polylines = contours.get(leaf, [])
        if not polylines:
            continue
        w = contour_widths[leaf]
        n_lines, n_pts = _author_ribbons(
            stage, f"{CAD_ROOT}/Contours/{leaf}", polylines, GROUP_COLOR[leaf],
            w, z_lift)
        counts[f"Contours/{leaf} ({interval} m, w={w:g})"] = (
            f"{n_lines} ribbons, {n_pts:,} verts")

    if len(spots):
        n = _author_markers(stage, f"{CAD_ROOT}/SpotHeights", spots,
                            GROUP_COLOR["SpotHeights"], spot_width, z_lift)
        counts["SpotHeights"] = f"{n} markers"

    if facilities:
        n_lines, n_pts = _author_ribbons(
            stage, f"{CAD_ROOT}/Facilities", facilities, GROUP_COLOR["Facilities"],
            contour_widths["c10"], z_lift)
        counts["Facilities"] = f"{n_lines} ribbons, {n_pts:,} verts"

    stage.GetRootLayer().Save()
    console.print(f"[green]wrote[/green] {out_path}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="build_cad_overlay",
        description=__doc__,
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "-i", "--dxf", type=Path,
        default=Path(r"D:\senckenberg\messel_karten\MESSEL.DXF"),
        help="Input DXF (default: messel_karten\\MESSEL.DXF).",
    )
    parser.add_argument(
        "-o", "--out", type=Path, default=Path("out/messel_cad.usd"),
        help="Output overlay USD (default out/messel_cad.usd).",
    )
    parser.add_argument(
        "-p", "--prep-dir", type=Path, default=Path("data/prep"),
        help="Dir holding origin.json (default data/prep).",
    )
    parser.add_argument(
        "-cw", "--contour-width", type=float, default=None,
        help="Set ALL contour ribbon widths (world metres) to this value. "
             "Per-interval flags below override it. Default: per-interval "
             f"defaults {DEFAULT_CONTOUR_WIDTHS}.",
    )
    parser.add_argument("-w025", "--width-c025", type=float, default=None,
                        help=f"0.25 m contour ribbon width (default {DEFAULT_CONTOUR_WIDTHS['c025']}).")
    parser.add_argument("-w05", "--width-c05", type=float, default=None,
                        help=f"0.5 m contour ribbon width (default {DEFAULT_CONTOUR_WIDTHS['c05']}).")
    parser.add_argument("-w10", "--width-c10", type=float, default=None,
                        help=f"1 m contour ribbon width (default {DEFAULT_CONTOUR_WIDTHS['c10']}).")
    parser.add_argument("-w50", "--width-c50", type=float, default=None,
                        help=f"5 m contour ribbon width (default {DEFAULT_CONTOUR_WIDTHS['c50']}).")
    parser.add_argument(
        "-sw", "--spot-width", type=float, default=6.0,
        help="Spot-height marker size in world metres (default 6).",
    )
    parser.add_argument(
        "-zl", "--z-lift", type=float, default=1.0,
        help="Metres to lift overlay geometry above its own Z so it sits on "
             "top of the terrain mesh and doesn't z-fight (default 1).",
    )
    parser.add_argument(
        "-nr", "--northing-restore", type=float, default=NORTHING_RESTORE,
        help=f"Value added to the truncated DXF northing before subtracting "
             f"the SW origin (default {NORTHING_RESTORE:.0f}, aligned to the "
             f"DEM pit floor).",
    )
    args = parser.parse_args()

    # Resolve per-interval contour widths: per-flag > --contour-width > default.
    base = args.contour_width
    contour_widths = {}
    for leaf in DEFAULT_CONTOUR_WIDTHS:
        per = getattr(args, f"width_{leaf}")
        contour_widths[leaf] = (
            per if per is not None
            else base if base is not None
            else DEFAULT_CONTOUR_WIDTHS[leaf]
        )

    console = Console()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    origin_path = args.prep_dir / "origin.json"
    if not origin_path.exists():
        raise FileNotFoundError(f"Missing {origin_path}. Run tools/prep_rasters.py first.")
    if not args.dxf.exists():
        raise FileNotFoundError(f"Missing {args.dxf}.")

    origin = json.loads(origin_path.read_text())
    sw_e = float(origin["utm_sw_easting"])
    sw_n = float(origin["utm_sw_northing"])
    width = float(origin["width_m"])
    height = float(origin["height_m"])

    console.print(f"Reading {args.dxf} ...")
    doc = ezdxf.readfile(str(args.dxf))

    contours, spots, facilities, stats = collect_geometry(
        doc, sw_e, sw_n, width, height, args.northing_restore, console)

    total_lines = sum(len(v) for v in contours.values()) + len(facilities)
    if total_lines == 0 and len(spots) == 0:
        raise SystemExit(
            "No survey geometry survived filtering -- the northing offset or "
            "layer names may be wrong for this DXF. Aborting (see spec's "
            "per-file bbox assertion).")

    # Bbox assertion: report where the kept geometry sits in the local frame.
    all_pts = [spots] if len(spots) else []
    for polys in contours.values():
        all_pts.extend(polys)
    all_pts.extend(facilities)
    stacked = np.concatenate(all_pts, axis=0)
    lx0, ly0, lz0 = stacked.min(axis=0)
    lx1, ly1, lz1 = stacked.max(axis=0)
    console.print(
        f"kept geometry local bbox: x[{lx0:.0f}..{lx1:.0f}] "
        f"y[{ly0:.0f}..{ly1:.0f}] z[{lz0:.1f}..{lz1:.1f}]  "
        f"(DEM is x[0..{width:.0f}] y[0..{height:.0f}])")
    if not (_in_bbox(lx0, ly0, width, height) and _in_bbox(lx1, ly1, width, height)):
        raise SystemExit(
            "Kept geometry falls outside the DEM bbox -- coordinate transform "
            "is wrong for this DXF. Check the northing-restore offset.")

    counts = author_stage(args.out, contours, spots, facilities, origin, console,
                          contour_widths=contour_widths, spot_width=args.spot_width,
                          z_lift=args.z_lift)

    summary = Table(title="CAD overlay build", show_header=False)
    summary.add_column(style="cyan")
    summary.add_column()
    summary.add_row("Source", str(args.dxf))
    summary.add_row("Stage", str(args.out))
    summary.add_row("Root prim", CAD_ROOT)
    for k, v in counts.items():
        summary.add_row(k, v)
    summary.add_row("Dropped (bad Z)", str(stats["dropped_z"]))
    summary.add_row("Dropped (out of bbox)", str(stats["dropped_bbox"]))
    console.print(summary)


if __name__ == "__main__":
    main()
