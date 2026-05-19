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

### 3. Build the USD (and .usdz)

```powershell
.venv\Scripts\python.exe -m messelpit.build_usd --usdz
```

Output: `out\messel.usd` + `out\ortho.png` (and `out\messel.usdz` if `--usdz`).

For first iteration on a slow machine, decimate the mesh:

```powershell
.venv\Scripts\python.exe -m messelpit.build_usd --decimate 4
```

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
tools/smoke_test.py            offline sanity check
data/                          (gitignored) raw + prepped rasters
out/                           (gitignored) final .usd / .usdz
```

## License of the produced USD

The geodata is dl-de/zero-2.0 (no attribution required). Code in this repo: MIT.
