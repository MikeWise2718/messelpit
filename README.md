# Messel Pit → USD

Build a textured USD heightfield of the **Grube Messel** UNESCO fossil site (Hesse, Germany)
from open Hessen state geodata, viewable in NVIDIA Omniverse.

Data:
- **DGM1** — 1 m LiDAR digital terrain model (HVBG, dl-de/zero-2.0)
- **DOP20** — 20 cm digital orthophoto (HVBG, dl-de/zero-2.0)

Both EPSG:25832 (ETRS89 / UTM 32N). Current coverage: ~6 × 9 km, 29 1 km tiles,
roughly easting 480 000..486 000 × northing 5 526 000..5 535 000. The exact tile
list lives in [`data/tile_manifest.txt`](data/tile_manifest.txt) — that's what
to feed into the HVBG shop on a fresh machine.

## Setup

```powershell
uv venv
uv pip install -e .
```

## Bootstrap on a new machine (laptop, etc.)

End-to-end from a fresh clone to a ready-to-view USD, skipping the
multi-GB full-res variant:

```powershell
git clone https://github.com/MikeWise2718/messelpit
cd messelpit
uv venv
uv pip install -e .

# Manual: download the 29 DGM1 + 29 DOP20 tiles from HVBG into
# data\raw\dgm1\ and data\raw\dop20\. See "Pipeline > 1. Download" below.
.venv\Scripts\python.exe tools\download_messel_data.py --open-browser

# Once tiles are in place:
.venv\Scripts\python.exe tools\prep_rasters.py
.\tools\build_variants.ps1 -SkipFullRes
```

Result: `out\messel_med.usd` (~65 MB, default for the desktop Kit viewer)
and `out\messel_lo.usd` (~16 MB, the Quest streaming target). The sibling
[messelpit_viewer](https://github.com/MikeWise2718/messelpit_viewer) repo
launches `messel_med.usd` automatically if cloned as a sibling directory.

Full step-by-step (with the manual HVBG download walkthrough) is below.

## Pipeline

### 1. Download the Hessen tiles (one-time, manual, ~10 min)

The HVBG Intershop is the only canonical distribution channel for DGM1 + DOP20
and uses a session-based order workflow (free, no login, but no stable per-tile
URL). So this step is manual on each fresh machine.

Open both shop pages (a helper exists to launch them in your default browser):

```powershell
.venv\Scripts\python.exe tools\download_messel_data.py --open-browser
```

Or open them directly:

- **DGM1** (1 m DEM): <https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/ViewDownloadcenter-Start?path=3D-Daten/Digitales+Gel%C3%A4ndemodell+(DGM1)>
- **DOP20** (0.2 m orthophoto): <https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/ViewDownloadcenter-Start?path=Luftbildinformationen/Digitale+Orthophotos+DOP20>

On each page:

1. Drill down: **Landkreis Darmstadt-Dieburg → Gemeinde Messel**, then go back
   and also do **Stadt Darmstadt** (the bbox crosses the city boundary).
2. Either use the map selector or, faster, the **filename search**: pick the
   29 tiles whose filenames are listed in [`data/tile_manifest.txt`](data/tile_manifest.txt).
   Tile names encode the SW corner in km — e.g. `dgm1_32_482_5530_1_he.tif` is
   the 1 km tile at UTM 32N easting 482 000, northing 5 530 000.
3. Add the tiles to your basket, accept the
   *Datenlizenz Deutschland – Zero – Version 2.0* terms, and place the free
   order (no login required since 2022).
4. Download the resulting ZIPs.
5. Unzip them so the DGM1 `.tif` + `.tfw` files land in `data\raw\dgm1\` and
   the DOP20 `.jpg` + `.jgw` files land in `data\raw\dop20\`. Flat layout — no
   subdirectories per tile.

Sanity check before going further:

```powershell
# Should show 29 + 29 (one each of .tif/.tfw, .jpg/.jgw per tile)
(Get-ChildItem data\raw\dgm1 -Filter *.tif).Count
(Get-ChildItem data\raw\dop20 -Filter *.jpg).Count
```

### 2. Mosaic + recenter to local meters

```powershell
.venv\Scripts\python.exe tools\prep_rasters.py
```

`prep_rasters.py` derives the bbox from whatever DGM1 tiles it finds, mosaics
DGM1 + DOP20 onto that bbox, drops the NIR channel of the ortho, and caps the
long texture axis at 16 384 px (the D3D12 / Omniverse RTX limit). Output:
`data\prep\dem.tif`, `data\prep\ortho.png`, `data\prep\origin.json`.

### 3. Build the USD variants

Four variants are built from the same DEM + texture: three mesh densities,
plus a Quest-targeted low-poly with a smaller bundled texture. The on-disk
`.usd` files all reference the same lossless `ortho.png`; the `.usdz`
bundles use a JPEG-compressed (and for `lo_quest` downsized) texture so
the packaged file is small enough to ship around.

| Variant                | Decimate | Verts  | Tris    | Tex inside `.usdz` | `.usd` | `.usdz` | Use                                  |
|------------------------|---------:|-------:|--------:|--------------------|-------:|--------:|--------------------------------------|
| `messel.usd`           | 1        | ~54 M  | ~108 M  | (rebuild)          | ~1 GB  | (rebuild) | Reference / offline renders          |
| `messel_med.usd`       | 4        | ~3.4 M | ~6.7 M  | 16384 JPEG q90     | ~65 MB | (rebuild) | **Default for desktop Kit viewer**   |
| `messel_lo.usd`        | 8        | ~840 K | ~1.7 M  | 16384 JPEG q90     | ~16 MB | **~44 MB** | Low-poly desktop / portable bundle  |
| `messel_lo_quest.usdz` | 8        | ~840 K | ~1.7 M  | 8192 JPEG q90      | (n/a)  | **~24 MB** | Quest 3 streaming target            |

Why four:

- The **full-res mesh** triggers a `device lost` GPU crash ~30 s after
  stage open on RTX 4080-class hardware in Omniverse Kit (works fine in
  `usdview`, which uses Storm/OpenGL). The med variant is what the
  sibling viewer repo's `launch.bat` defaults to.
- The **`.usdz` files JPEG the texture at q90** rather than embedding the
  lossless PNG. On aerial orthophotos this is visually indistinguishable
  from PNG and drops the bundle size by roughly 4× — enough to put
  `messel_lo.usdz` under GitHub's 50 MB recommendation. The on-disk
  `ortho.png` is unaffected.
- The **Quest variant** also halves the texture's long axis (16384 → 8192).
  Quest 3 over Air Link has lower effective texture bandwidth than a
  desktop GPU, and at the bbox scale (6 × 9 km, viewed mostly from above)
  the detail loss is imperceptible in VR.

Build all four with one command:

```powershell
.\tools\build_variants.ps1
```

This skips variants that already exist (incremental re-runs are cheap).
Useful flags:

- `-Force` — rebuild everything from scratch
- `-SkipFullRes` — only build med + lo + lo_quest (the variants you actually use day-to-day)
- `-NoUsdz` — don't pack `.usdz` (faster, skips the JPEG texture step; also skips lo_quest since it only ships as `.usdz`)

Or build a single variant directly:

```powershell
# Desktop low-poly bundle at 16384 JPEG q90 → ~44 MB
.venv\Scripts\python.exe -m messelpit.build_usd `
    --decimate 8 --out out\messel_lo.usd --usdz `
    --texture-format jpeg --texture-quality 90 --texture-max-dim 16384

# Quest variant at 8192 JPEG q90 → ~24 MB
.venv\Scripts\python.exe -m messelpit.build_usd `
    --decimate 8 --out out\messel_lo_quest.usd --usdz `
    --texture-format jpeg --texture-quality 90 --texture-max-dim 8192
```

Texture flags (apply only to the `.usdz`; the loose `.usd` always
references the original lossless `ortho.png`):

- `--texture-format {png,jpeg}` (`-tf`) — format inside the `.usdz`. Default `png` (lossless, large).
- `--texture-quality N` (`-tq`) — JPEG quality 1..100. Default 90 (visually lossless for orthophotos).
- `--texture-max-dim N` (`-td`) — cap the long axis of the `.usdz` texture (Lanczos resize). Default: keep source size.

Output: `out\messel*.usd` + `out\messel*.usdz` + `out\ortho.png` (copied from
`data\prep\ortho.png` so the loose USD's relative texture reference
resolves).

## Verifying the pipeline without the Hessen download

```powershell
.venv\Scripts\python.exe tools\smoke_test.py
```
Generates a 300 × 300 m synthetic pit and builds `out\demo\demo.usd`.

## Opening in Omniverse

1. Launch Omniverse USD Composer (or Create / View).
2. `File → Open` → `out\messel.usd`.
3. The terrain prim is at `/World/Terrain`. The orthophoto is wired through a
   `UsdPreviewSurface` so any renderer that handles preview-surface (RTX, Storm,
   Karma) will show it.
4. The stage uses **Z-up**, **meters**, origin at the SW corner of the bbox.
   Original UTM coordinates are stored in `customData` on `/World` and in
   `data\prep\origin.json`.

## Layout

```
specs/messel-pit-usd.md        full design spec
src/messelpit/__init__.py      __version__
src/messelpit/build_usd.py     mesh + material authoring
tools/download_messel_data.py  opens HVBG shop pages
tools/prep_rasters.py          mosaic/crop/recenter
tools/build_variants.ps1       build full / med / lo USD variants
tools/smoke_test.py            offline sanity check
data/                          (gitignored) raw + prepped rasters
out/                           (gitignored) final .usd / .usdz
```

## License of the produced USD

The geodata is dl-de/zero-2.0 (no attribution required). Code in this repo: MIT.
