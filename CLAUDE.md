# CLAUDE.md — Messel Pit Data Pipeline

Project-specific guidance for Claude sessions working in this repo. Read this
alongside the global `~/.claude/CLAUDE.md`.

## What this project is

A Python data pipeline that converts open Hessen state geodata into a
textured USD heightfield of the **Grube Messel** UNESCO World Heritage
fossil site (near Darmstadt, Hesse):

- **DGM1** — 1 m LiDAR digital terrain model (HVBG, dl-de/zero-2.0)
- **DOP20** — 20 cm RGBI orthophoto (HVBG, dl-de/zero-2.0)
- **Output** — `out\messel.usd` + `out\ortho.png` (+ `.usdz`)

The user (Mike Wise) works with the **Senckenberg Research Institute**
(operators of the Messel Pit). The eventual deliverable is a **Meta Quest 3
VR experience** of the site, streamed via CloudXR.js / WebXR in the Quest
browser. **This repo only produces the USD asset.** The Kit viewer
application that loads it lives in the sibling repo.

## Sibling repo

```
D:\senckenberg\
├── messelpit\          ← you are here (data pipeline, Python/uv)
│   └── out\messel.usd  ← what this repo produces
└── messelpit_viewer\   ← NVIDIA Omniverse Kit app (vendored kit-app-template)
    └── launch.bat      ← references ..\messelpit\out\messel_med.usd
```

GitHub: [`MikeWise2718/messelpit`](https://github.com/MikeWise2718/messelpit) +
[`MikeWise2718/messelpit_viewer`](https://github.com/MikeWise2718/messelpit_viewer).

The two repos are loose-coupled. The viewer reads the USD at launch time
via a relative path; no build-time dependency.

## Pipeline shape

1. **`tools/download_messel_data.py`** — opens the HVBG Intershop in a
   browser. The shop uses session-based orders (free, no login, but no
   stable URLs), so this step is manual. Tiles to download are listed in
   `data/tile_manifest.txt`.
2. **`tools/prep_rasters.py`** — mosaics + recenters DGM1 + DOP20 onto a
   local-meters bbox. Bbox is derived from whatever tiles are present —
   no hardcoded coordinates.
3. **`src/messelpit/build_usd.py`** — authors the USD heightfield mesh
   with a `UsdPreviewSurface` material referencing `ortho.png` via UV.

## Three USD variants

`build_usd.py --decimate N` produces meshes at different densities. We
generate three:

| Variant | Decimate | Verts | Tris | Size | Use |
|---|---|---|---|---|---|
| `messel.usd` | 1 | ~54M | ~108M | ~1 GB | Reference / offline renders |
| `messel_med.usd` | 4 | ~3.4M | ~6.75M | ~250 MB | **Default for desktop Kit** |
| `messel_lo.usd` | 8 | ~840K | ~1.5M | ~50 MB | Quest streaming target |

Why three: the full-res mesh triggers a `device lost` GPU crash ~30 s
after stage open on RTX 4080-class hardware in Kit (works fine in
`usdview`, which uses Storm/OpenGL). The med variant is the default for
desktop iteration in the viewer repo.

## Constraints to keep in mind

- **D3D12 / RTX `Texture2D` limit is 16384 px per axis.** Native DOP20
  over the 6×9 km bbox is ~30000 × 45000 — too big. `prep_rasters.py`
  caps the long axis at 16384 by default (effective ~0.55 m/px). **If the
  cap is removed, Kit silently fails to upload the texture** — terrain
  renders as solid grey. Works fine in `usdview` (Storm/OpenGL has a
  higher cap), which is misleading.
- **Z-up, meters, SW corner at local origin.** Stage settings authored
  in `build_usd.py` must agree with what the viewer expects. Don't
  switch to Y-up.
- **Texture is referenced by relative path** (`./ortho.png`). `messel.usd`
  + `ortho.png` must stay co-located. The build script copies `ortho.png`
  into `out/` for this reason.

## Coverage

The current build covers an **irregular ~6 × 9 km area** (29 tiles), not
the 3 × 3 km that the spec originally proposed. The spec was updated to
reflect this. Tile filenames are in `data/tile_manifest.txt` (tracked in
git, despite being under the otherwise-gitignored `data/` directory —
there's a negation rule in `.gitignore`).

If the coverage changes, regenerate the manifest from `data/raw/dgm1/`
and `data/raw/dop20/` and update the count in the spec + README.

## What NOT to put in git

`.gitignore` excludes `data/raw/`, `data/prep/`, and `out/` because they're
multi-GB. **Only `data/tile_manifest.txt` is tracked under `data/`** (via
`!data/tile_manifest.txt` negation). A fresh clone gets the code + the tile
list, then has to re-download from HVBG.

## Conventions specific to this repo

- **Python via `uv`** (per global preferences). Virtual env at `.venv/`.
- **`rich` + `rich-argparse`** for CLI output and help.
- **Short-form CLI args**: one-letter for common (`-o`, `-i`, `-d`),
  two-letter for project-specific (`-mt` for `--max-tex-dim`, etc.).
- **`pyproject.toml` lists deps** including `usd-core` (we author USD
  without a full Omniverse SDK install) and `rasterio` for geodata.

## What to ask before changing

- Changing the bbox / coverage: ask first. The current 29-tile manifest
  reflects deliberate choices about what context to include around the pit.
- Switching CRS or unit system: ask. UTM 32N + DHHN2016 heights + Z-up
  meters is what the viewer expects.
- Adding new output formats (FBX, glTF, etc.): ask. USD is the format the
  viewer wants; we keep `.usdz` as a portability artifact only.

## References

- Viewer repo: <https://github.com/MikeWise2718/messelpit_viewer>
- Spec: `specs/messel-pit-usd.md`
- HVBG download center (DGM1): <https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/ViewDownloadcenter-Start?path=3D-Daten/Digitales+Gel%C3%A4ndemodell+(DGM1)>
- HVBG download center (DOP20): <https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/ViewDownloadcenter-Start?path=Luftbildinformationen/Digitale+Orthophotos+DOP20>
- USD Composer / OpenUSD docs: <https://openusd.org/release/index.html>
- Senckenberg Research Institute: <https://www.senckenberg.de/>
