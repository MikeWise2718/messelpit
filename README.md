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

```powershell
# 1. Download (one-time, manual; opens shop pages in your browser)
.venv\Scripts\python.exe tools\download_messel_data.py --open-browser
#    Use the map selector, accept dl-de/zero-2.0, download both ZIPs,
#    unzip into data\raw\dgm1\ and data\raw\dop20\.

# 2. Mosaic + crop + recenter to local meters
.venv\Scripts\python.exe tools\prep_rasters.py

# 3. Build the USD (and .usdz)
.venv\Scripts\python.exe -m messelpit.build_usd --usdz

# Result: out\messel.usd + out\ortho.png  (and out\messel.usdz)
```

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
