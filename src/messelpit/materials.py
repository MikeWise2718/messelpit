"""Shared material helpers.

One job: make sure every surface we author is actually MATTE.

The bug this exists to prevent
==============================

`UsdPreviewSurface`'s dielectric specular response ramps toward 1.0 at glancing
angles **no matter the roughness**. That is Fresnel, and it is driven by `ior`,
whose default is **1.5**. Setting only `roughness` -- the intuitive thing to do --
does not touch it.

Terrain and draped overlays are viewed from low, raking angles across a whole
landscape, which is exactly the regime where that lobe blows out: the surface
flares white and reads as "the scene is washing out".

This exact one-liner has now shipped **five** times across this project, in five
independent material authors, because each one reached for `roughness`:

  1. the Kalahari terrain material           (Kalahari_dt)
  2. all 59 osm2usd materials                (osm2usd/materials.py::_set_matte)
  3. the DataDrape materials                 (usd_viewer lion_tracks_gen)
  4. the Messel TERRAIN material             (build_usd.py -- roughness=0.9, no ior)
  5. the Messel map + CAD overlay materials  (build_map_overlay, build_cad_overlay)

So it lives in one function now, and the three messelpit authors call it.

See `usd_viewer/specs/default-lighting.md` for the full post-mortem -- including
the separate lighting misdiagnosis this symptom kept getting confused with.
"""
from __future__ import annotations

from pxr import Gf, Sdf, UsdShade


def set_matte(pbr: UsdShade.Shader) -> None:
    """Kill the grazing-angle specular white-out on a UsdPreviewSurface.

    `ior=1` is the load-bearing one: it removes the index mismatch, so there is no
    Fresnel edge at any viewing angle. The rest zero the residual lobe.

    Call this on every PBR shader you author. It is safe to call before or after
    setting diffuseColor / emissiveColor -- it touches neither.
    """
    pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    pbr.CreateInput("ior", Sdf.ValueTypeNames.Float).Set(1.0)
    pbr.CreateInput("specularColor", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(0.0, 0.0, 0.0)
    )
