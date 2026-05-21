"""Build a USD heightfield mesh of the Messel Pit and drape the orthophoto over it.

Reads data/prep/dem.tif and data/prep/ortho.png produced by tools/prep_rasters.py.
Outputs out/messel.usd (and optionally .usdz).

The mesh is a regular grid: one vertex per DEM pixel, two triangles per cell.
UVs are simply (col/N, 1 - row/N) so the orthophoto wraps exactly onto the grid.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import rasterio
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils, Vt
from rich.console import Console
from rich.table import Table
from rich_argparse import RichHelpFormatter

from messelpit import __version__


def build_grid_mesh(dem: np.ndarray, res_m: float, decimate: int):
    """Return (points, face_vertex_counts, face_vertex_indices, uvs) for a DEM grid."""
    if decimate > 1:
        dem = dem[::decimate, ::decimate]
        res_m = res_m * decimate
    H, W = dem.shape
    ys, xs = np.mgrid[0:H, 0:W]
    # World coords: x = col * res, y = (H-1-row) * res so that +Y is north.
    px = (xs * res_m).astype(np.float32)
    py = ((H - 1 - ys) * res_m).astype(np.float32)
    pz = dem.astype(np.float32)
    points = np.stack([px, py, pz], axis=-1).reshape(-1, 3)

    # Two triangles per quad. Vertex order so normals point +Z.
    # Quad at (r, c) uses verts:  v00=(r,c)  v10=(r+1,c)  v01=(r,c+1)  v11=(r+1,c+1)
    r = np.arange(H - 1)
    c = np.arange(W - 1)
    rr, cc = np.meshgrid(r, c, indexing="ij")
    v00 = rr * W + cc
    v10 = (rr + 1) * W + cc
    v01 = rr * W + (cc + 1)
    v11 = (rr + 1) * W + (cc + 1)
    tri1 = np.stack([v00, v10, v11], axis=-1)
    tri2 = np.stack([v00, v11, v01], axis=-1)
    indices = np.concatenate([tri1.reshape(-1, 3), tri2.reshape(-1, 3)], axis=0)
    face_vertex_indices = indices.reshape(-1).astype(np.int32)
    face_vertex_counts = np.full(indices.shape[0], 3, dtype=np.int32)

    # UVs: per-vertex. (u,v) = (col/(W-1), row/(H-1)) — image origin is top-left,
    # USD UV origin is bottom-left, so flip v.
    u = (xs / max(W - 1, 1)).astype(np.float32)
    v = 1.0 - (ys / max(H - 1, 1)).astype(np.float32)
    uvs = np.stack([u, v], axis=-1).reshape(-1, 2)

    return points, face_vertex_counts, face_vertex_indices, uvs


def author_stage(out_path: Path, dem: np.ndarray, res_m: float,
                 ortho_rel_path: str, origin_meta: dict, decimate: int,
                 console: Console) -> None:
    stage = Usd.Stage.CreateNew(str(out_path))
    stage.SetMetadata("metersPerUnit", 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))

    world = UsdGeom.Xform.Define(stage, "/World")
    world.GetPrim().SetCustomDataByKey("messelpit:version", __version__)
    world.GetPrim().SetCustomDataByKey("messelpit:origin", origin_meta)

    points, fvc, fvi, uvs = build_grid_mesh(dem, res_m, decimate)
    console.print(
        f"Mesh: {len(points):,} verts, {len(fvc):,} tris  "
        f"(decimate={decimate}, res={res_m:.2f} m)"
    )

    mesh = UsdGeom.Mesh.Define(stage, "/World/Terrain")
    mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(fvc))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(fvi))
    mesh.CreateSubdivisionSchemeAttr("none")
    z_min = float(dem.min()); z_max = float(dem.max())
    H, W = dem.shape
    mesh.CreateExtentAttr(Vt.Vec3fArray([
        Gf.Vec3f(0.0, 0.0, z_min),
        Gf.Vec3f(float((W - 1) * res_m), float((H - 1) * res_m), z_max),
    ]))

    primvars_api = UsdGeom.PrimvarsAPI(mesh)
    st = primvars_api.CreatePrimvar(
        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex,
    )
    st.Set(Vt.Vec2fArray.FromNumpy(uvs))

    material = UsdShade.Material.Define(stage, "/World/Terrain/Mat")
    pbr = UsdShade.Shader.Define(stage, "/World/Terrain/Mat/PBR")
    pbr.CreateIdAttr("UsdPreviewSurface")
    pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.9)
    pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

    st_reader = UsdShade.Shader.Define(stage, "/World/Terrain/Mat/StReader")
    st_reader.CreateIdAttr("UsdPrimvarReader_float2")
    st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

    tex = UsdShade.Shader.Define(stage, "/World/Terrain/Mat/DiffuseTex")
    tex.CreateIdAttr("UsdUVTexture")
    tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(ortho_rel_path)
    tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
        st_reader.ConnectableAPI(), "result")
    tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("clamp")
    tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("clamp")
    tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

    pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
        tex.ConnectableAPI(), "rgb")
    material.CreateSurfaceOutput().ConnectToSource(pbr.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)

    stage.GetRootLayer().Save()
    console.print(f"[green]wrote[/green] {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="build_usd",
        description=__doc__,
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("-i", "--prep-dir", type=Path, default=Path("data/prep"))
    parser.add_argument("-o", "--out", type=Path, default=Path("out/messel.usd"))
    parser.add_argument("-d", "--decimate", type=int, default=1,
                        help="Stride for subsampling the DEM (1 = full 1m grid).")
    parser.add_argument("-z", "--usdz", action="store_true",
                        help="Also produce a portable .usdz next to the .usd.")
    args = parser.parse_args()

    console = Console()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    smooth_path = Path("vegetation_troubleshooting/dem_smooth.tif")
    dem_path = smooth_path if smooth_path.exists() else args.prep_dir / "dem.tif"
    if smooth_path.exists():
        console.print(f"[cyan]Using smoothed DEM:[/cyan] {smooth_path}")
    ortho_path = args.prep_dir / "ortho.png"
    origin_path = args.prep_dir / "origin.json"
    for p in (dem_path, ortho_path, origin_path):
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}. Run tools/prep_rasters.py first.")

    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        res_m = abs(src.transform.a)

    origin_meta = json.loads(origin_path.read_text())

    # Copy ortho.png next to the .usd so the texture reference is portable.
    ortho_target = args.out.parent / ortho_path.name
    if ortho_target.resolve() != ortho_path.resolve():
        shutil.copy2(ortho_path, ortho_target)

    author_stage(
        out_path=args.out,
        dem=dem,
        res_m=res_m,
        ortho_rel_path=f"./{ortho_path.name}",
        origin_meta=origin_meta,
        decimate=args.decimate,
        console=console,
    )

    summary = Table(title="USD build", show_header=False)
    summary.add_column(style="cyan")
    summary.add_column()
    summary.add_row("Stage",      str(args.out))
    summary.add_row("Texture",    str(ortho_target))
    summary.add_row("Up axis",    "Z")
    summary.add_row("Units",      "meters")
    summary.add_row("DEM stats",  f"{origin_meta['dem_stats']['min']:.1f} .. "
                                  f"{origin_meta['dem_stats']['max']:.1f} m")
    console.print(summary)

    if args.usdz:
        usdz_path = args.out.with_suffix(".usdz")
        UsdUtils.CreateNewUsdzPackage(str(args.out), str(usdz_path))
        console.print(f"[green]wrote[/green] {usdz_path}")


if __name__ == "__main__":
    main()
