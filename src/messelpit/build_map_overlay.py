"""Author a USD overlay that drapes a georeferenced raster map on the terrain.

Phase 2 of the legacy-CAD/map overlays (see
``specs/legacy-cad-and-map-overlays.md``). Takes ``Planquad.psd`` -- the
50 m planquadrat excavation grid + contour map (Schaal & Müller 1991) --
converts it to a transparent RGBA texture (white grid lines opaque, black
background transparent), and authors a **draped, DEM-sampled quad** under
``/World/Maps/Planquad`` so the grid follows the pit relief instead of
floating as a flat sheet.

Like the CAD overlay, the result is a pristine stage referenced by the
wrapper (``build_overlay_stage.py --maps``); the viewer toggles it via the
sidecar "Survey" tab. Same Z-up/metres/SW-corner frame -- no transform on
the reference.

Georeferencing
--------------
``Planquad.psd`` has no world file, but it prints its own grid coordinates
on the axes (eastings 82xxx, northings 3xxxx -- truncated UTM 32N). The
grid rectangle's pixel corners were read off the image and tied to those
labels, then mapped to the scene local frame. The result lands on the
same rectangle as the Phase-1 DXF contours (local x≈2300..3196,
y≈3132..4132), confirming the alignment.

The pixel→local affine for the cropped texture (``out/planquad.png``, which
is cropped exactly to the grid rectangle) is therefore just the grid
corners below; the texture's UV (0..1) maps linearly across them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt
from rich.console import Console
from rich.table import Table
from rich_argparse import RichHelpFormatter

from messelpit import __version__

Image.MAX_IMAGE_PIXELS = None

MAPS_ROOT = "/World/Maps"

#: Prim path the viewer's nudge controls (transform_list tab) write offsets
#: against in <usd>.nudge.json. The builder reads this entry to bake an
#: interactively-dialed offset into the source rectangle. See the bake-back
#: loop in specs/legacy-cad-and-map-overlays.md.
PLANQUAD_PRIM = "/World/Maps/Planquad"


def _read_nudge_file(path: Path, prim: str, console: Console):
    """Read [dx, dy, dz] (metres) for `prim` from a viewer .nudge.json.

    The viewer bakes interactive nudges to <usd>.nudge.json as
    {prim_path: [dx, dy, dz]}. Returns (dx, dy, dz) or (0,0,0) if the file
    or the entry is absent. dz folds into z_lift; dx/dy shift the rectangle.
    """
    if not path.exists():
        console.print(f"[yellow]nudge file not found:[/yellow] {path} (using flag defaults)")
        return 0.0, 0.0, 0.0
    try:
        data = json.loads(path.read_text())
        off = data.get(prim)
        if isinstance(off, (list, tuple)) and len(off) == 3:
            dx, dy, dz = float(off[0]), float(off[1]), float(off[2])
            console.print(
                f"[green]nudge file[/green] {path.name}: {prim} -> "
                f"dx={dx:g} dy={dy:g} dz={dz:g} m")
            return dx, dy, dz
        console.print(f"[yellow]nudge file has no entry for {prim}[/yellow]")
    except Exception as exc:
        console.print(f"[red]nudge file read failed:[/red] {path}: {exc}")
    return 0.0, 0.0, 0.0

# Planquad grid rectangle in the scene LOCAL frame (Z-up metres, SW-corner
# origin). Derived by reading the printed axis coordinates off Planquad.psd
# and reconciling against the Phase-1 DXF bbox (see module docstring + spec).
# These bound the cropped texture out/planquad.png.
#
# Anchored to the PSD's own printed grid labels (E 482300..483200,
# N 5530900..5531900 after restoring the truncated digits). BUT the label-
# derived placement put the grid ~1 cell (50 m) too far EAST of the pit
# (caught by eye in the viewer; the DXF contours and the PSD's own contours
# DO match shape -- same survey -- so it's a registration offset, likely an
# off-by-one in which gridline the easting label sits against, or a small
# error in the source map's printed coordinates). Corrected by shifting the
# rectangle 50 m west. Fine-tune empirically with --dx/--dy.
_NUDGE_DX = -50.0   # metres; negative = west
_NUDGE_DY = 0.0     # metres; positive = north
PLANQUAD_LOCAL = {
    "x_min": 2300.0, "x_max": 3200.0,
    "y_min": 3132.0, "y_max": 4132.0,
}


def _sample_dem(dem: np.ndarray, res_m: float, xs: np.ndarray, ys: np.ndarray):
    """Bilinear-ish (nearest) DEM elevation at local (x, y) metre coords.

    DEM grid: x = col*res, y = (H-1-row)*res (matches build_usd.py). Returns
    z per query point, NaN-safe (clamps to valid range).
    """
    H, W = dem.shape
    col = np.clip((xs / res_m).round().astype(int), 0, W - 1)
    row = np.clip((H - 1 - ys / res_m).round().astype(int), 0, H - 1)
    z = dem[row, col].astype(np.float32)
    return z


def build_draped_quad(dem: np.ndarray, res_m: float, rect: dict,
                      subdiv: int, z_lift: float):
    """Return (points, fvc, fvi, uvs) for a draped, DEM-sampled quad.

    ``subdiv`` cells per side (e.g. 64 -> 65x65 vertex grid). Each vertex
    sits on the DEM surface + ``z_lift`` so the map hugs the relief.
    """
    n = subdiv + 1
    xs = np.linspace(rect["x_min"], rect["x_max"], n)
    ys = np.linspace(rect["y_min"], rect["y_max"], n)
    gx, gy = np.meshgrid(xs, ys)  # (n,n)
    gz = _sample_dem(dem, res_m, gx.ravel(), gy.ravel()).reshape(n, n) + z_lift
    points = np.stack([gx, gy, gz], axis=-1).reshape(-1, 3).astype(np.float32)

    # UVs: u across x (west->east), v up y (south->north). USD UV origin is
    # bottom-left; the texture's row 0 is its TOP (north), so v must flip to
    # put north at the top of the image. north = max y = last row here.
    u = ((gx - rect["x_min"]) / (rect["x_max"] - rect["x_min"])).reshape(-1)
    v = ((gy - rect["y_min"]) / (rect["y_max"] - rect["y_min"])).reshape(-1)
    uvs = np.stack([u, v], axis=-1).astype(np.float32)

    # Faces: two tris per cell.
    r = np.arange(n - 1)
    c = np.arange(n - 1)
    rr, cc = np.meshgrid(r, c, indexing="ij")
    v00 = rr * n + cc
    v10 = (rr + 1) * n + cc
    v01 = rr * n + (cc + 1)
    v11 = (rr + 1) * n + (cc + 1)
    tri1 = np.stack([v00, v10, v11], axis=-1)
    tri2 = np.stack([v00, v11, v01], axis=-1)
    fvi = np.concatenate([tri1.reshape(-1, 3), tri2.reshape(-1, 3)], axis=0).reshape(-1)
    fvc = np.full(fvi.shape[0] // 3, 3, dtype=np.int32)
    return points, fvc.astype(np.int32), fvi.astype(np.int32), uvs


def author_stage(out_path: Path, dem: np.ndarray, res_m: float, rect: dict,
                 tex_rel: str, prim_leaf: str, subdiv: int, z_lift: float,
                 console: Console) -> dict:
    stage = Usd.Stage.CreateNew(str(out_path))
    stage.SetMetadata("metersPerUnit", 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))
    UsdGeom.Xform.Define(stage, MAPS_ROOT)

    prim_path = f"{MAPS_ROOT}/{prim_leaf}"
    points, fvc, fvi, uvs = build_draped_quad(dem, res_m, rect, subdiv, z_lift)

    mesh = UsdGeom.Mesh.Define(stage, prim_path)
    mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(fvc))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(fvi))
    mesh.CreateSubdivisionSchemeAttr("none")
    mesh.CreateDoubleSidedAttr(True)
    mn = [float(v) for v in points.min(axis=0)]
    mx = [float(v) for v in points.max(axis=0)]
    mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*mn), Gf.Vec3f(*mx)]))

    st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(
        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
    st.Set(Vt.Vec2fArray.FromNumpy(uvs))

    # Material: texture with alpha -> opacity, emissive so lines read on ortho.
    mat = UsdShade.Material.Define(stage, f"{prim_path}/Mat")
    pbr = UsdShade.Shader.Define(stage, f"{prim_path}/Mat/PBR")
    pbr.CreateIdAttr("UsdPreviewSurface")
    pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

    reader = UsdShade.Shader.Define(stage, f"{prim_path}/Mat/StReader")
    reader.CreateIdAttr("UsdPrimvarReader_float2")
    reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

    tex = UsdShade.Shader.Define(stage, f"{prim_path}/Mat/Tex")
    tex.CreateIdAttr("UsdUVTexture")
    tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(tex_rel)
    tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
        reader.ConnectableAPI(), "result")
    tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("clamp")
    tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("clamp")
    tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    tex.CreateOutput("a", Sdf.ValueTypeNames.Float)

    pbr.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
        tex.ConnectableAPI(), "rgb")
    pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
        tex.ConnectableAPI(), "rgb")
    pbr.CreateInput("opacity", Sdf.ValueTypeNames.Float).ConnectToSource(
        tex.ConnectableAPI(), "a")
    mat.CreateSurfaceOutput().ConnectToSource(pbr.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)

    survey = stage.GetPrimAtPath(MAPS_ROOT)
    survey.SetCustomDataByKey("messelpit:map_overlay_version", __version__)

    stage.GetRootLayer().Save()
    console.print(f"[green]wrote[/green] {out_path}")
    return {"verts": len(points), "tris": len(fvc),
            "local bbox": f"x[{mn[0]:.0f}..{mx[0]:.0f}] y[{mn[1]:.0f}..{mx[1]:.0f}] z[{mn[2]:.0f}..{mx[2]:.0f}]"}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="build_map_overlay", description=__doc__,
        formatter_class=RichHelpFormatter)
    parser.add_argument(
        "-t", "--texture", type=Path, default=Path("out/planquad.png"),
        help="RGBA texture (transparent bg) for the map (default out/planquad.png).")
    parser.add_argument(
        "-o", "--out", type=Path, default=Path("out/messel_maps.usd"),
        help="Output overlay USD (default out/messel_maps.usd).")
    parser.add_argument(
        "-p", "--prep-dir", type=Path, default=Path("data/prep"),
        help="Dir holding dem.tif + origin.json (default data/prep).")
    parser.add_argument(
        "-l", "--leaf", default="Planquad",
        help="Prim leaf under /World/Maps (default Planquad).")
    parser.add_argument(
        "-s", "--subdiv", type=int, default=96,
        help="Quad subdivisions per side for DEM draping (default 96).")
    parser.add_argument(
        "-zl", "--z-lift", type=float, default=1.5,
        help="Metres above the DEM surface (default 1.5; sits above contours).")
    parser.add_argument(
        "-dx", "--dx", type=float, default=_NUDGE_DX,
        help=f"East/west registration nudge in metres (default {_NUDGE_DX:g}; "
             "negative = west). Shifts the whole grid rectangle.")
    parser.add_argument(
        "-dy", "--dy", type=float, default=_NUDGE_DY,
        help=f"North/south registration nudge in metres (default {_NUDGE_DY:g}; "
             "positive = north).")
    parser.add_argument(
        "-nf", "--nudge-file", type=Path, default=None,
        help="Viewer-authored <usd>.nudge.json to bake in. Its [dx,dy,dz] for "
             f"{PLANQUAD_PRIM} is ADDED to --dx/--dy (dz folds into --z-lift). "
             "This is the bake-back path: nudge in the viewer, then rebuild "
             "with this flag to fold the offset into the source asset.")
    args = parser.parse_args()

    console = Console()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    dem_path = args.prep_dir / "dem.tif"
    origin_path = args.prep_dir / "origin.json"
    for p in (dem_path, origin_path, args.texture):
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}.")

    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        res_m = abs(src.transform.a)
    origin = json.loads(origin_path.read_text())
    width = float(origin["width_m"]); height = float(origin["height_m"])

    # Fold a viewer-baked nudge (if supplied) on top of the flag defaults.
    bake_dx, bake_dy, bake_dz = (0.0, 0.0, 0.0)
    if args.nudge_file is not None:
        bake_dx, bake_dy, bake_dz = _read_nudge_file(
            args.nudge_file, PLANQUAD_PRIM, console)

    total_dx = args.dx + bake_dx
    total_dy = args.dy + bake_dy
    total_zlift = args.z_lift + bake_dz

    rect = {
        "x_min": PLANQUAD_LOCAL["x_min"] + total_dx,
        "x_max": PLANQUAD_LOCAL["x_max"] + total_dx,
        "y_min": PLANQUAD_LOCAL["y_min"] + total_dy,
        "y_max": PLANQUAD_LOCAL["y_max"] + total_dy,
    }
    console.print(
        f"registration nudge: dx={total_dx:g} dy={total_dy:g} m "
        f"(flags {args.dx:g}/{args.dy:g} + bake {bake_dx:g}/{bake_dy:g}); "
        f"z_lift={total_zlift:g} m")
    # Sanity: the grid rectangle must sit inside the DEM bbox.
    if not (0 <= rect["x_min"] and rect["x_max"] <= width
            and 0 <= rect["y_min"] and rect["y_max"] <= height):
        raise SystemExit(
            f"Planquad rect {rect} falls outside DEM bbox "
            f"(0..{width} x 0..{height}); check georeferencing.")

    # Copy texture next to the USD so the relative ref resolves.
    tex_target = args.out.parent / args.texture.name
    if tex_target.resolve() != args.texture.resolve():
        import shutil
        shutil.copy2(args.texture, tex_target)

    info = author_stage(args.out, dem, res_m, rect, f"./{args.texture.name}",
                        args.leaf, args.subdiv, total_zlift, console)

    summary = Table(title="Map overlay build", show_header=False)
    summary.add_column(style="cyan"); summary.add_column()
    summary.add_row("Texture", str(args.texture))
    summary.add_row("Stage", str(args.out))
    summary.add_row("Prim", f"{MAPS_ROOT}/{args.leaf}")
    for k, v in info.items():
        summary.add_row(k, str(v))
    console.print(summary)


if __name__ == "__main__":
    main()
