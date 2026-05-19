# Messel Pit — LiDAR DEM + Orthophoto → Omniverse USD

Build a USD scene of the **Grube Messel** UNESCO fossil site (near Darmstadt, Hesse) as a
heightfield mesh derived from the Hessen state 1 m LiDAR DEM (DGM1), textured with the
Hessen 20 cm orthophoto (DOP20). Open in NVIDIA Omniverse.

## Site

- Name: Grube Messel (Messel Pit)
- WGS84: ~49.9172° N, 8.7556° E
- ETRS89 / UTM 32N (EPSG:25832): easting ~482 100, northing ~5 529 800
- Extent (current build): irregular ~6 × 9 km area covering the pit and surrounding
  landscape (Messel village, Darmstadt fringe, etc.)
  - East range: 480 000 .. 486 000 (6 km)
  - North range: 5 526 000 .. 5 535 000 (9 km)
  - Covers **29 DGM1 tiles** and 29 DOP20 tiles (1 km × 1 km each)
  - The exact tile list is tracked in `data/tile_manifest.txt`
  - Original (smaller) plan was 3 × 3 km / 16 tiles centered on the pit (480 600 ..
    483 600 E × 5 528 300 .. 5 531 300 N); the build was later expanded for context.
  - `tools/prep_rasters.py` derives the bbox from whatever tiles are present, so
    swapping the coverage just means downloading a different tile set.

## Data sources

All under **Datenlizenz Deutschland – Zero – Version 2.0** (no attribution required, free
commercial reuse). Provider: Hessische Verwaltung für Bodenmanagement und Geoinformation
(HVBG).

### DGM1 — 1 m digital terrain model

- Format: GeoTIFF, 32-bit float, LZW compressed, NoData = -9999
- CRS: ETRS89 / UTM 32N (EPSG:25832) + heights DHHN2016
- Vertical accuracy: ±0.3 m
- Tile size: 1 km × 1 km
- Download center: <https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/ViewDownloadcenter-Start?path=3D-Daten/Digitales+Gel%C3%A4ndemodell+(DGM1)>
- Metadata: <https://www.metaver.de/trefferanzeige?docuuid=dbf48a95-b44d-48b3-a5b4-981e4c1bd8e6>

### DOP20 — 20 cm digital orthophoto

- Format: GeoTIFF, RGBI 4-channel (visible + near-infrared)
- CRS: ETRS89 / UTM 32N (EPSG:25832)
- Tile size: 1 km × 1 km (typical for HE)
- Download center: <https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/ViewDownloadcenter-Start?path=Luftbildinformationen/Digitale+Orthophotos+DOP20>
- Metadata: <https://gdk.gdi-de.org/geonetwork/srv/api/records/0b30f537-3bd0-44d4-83b0-e3c1542ca265>

### Why not pure-URL scripted download?

The HVBG Intershop download center is the only canonical distribution channel and uses a
**session-based order workflow** (free, but no stable per-tile URL). INSPIRE ATOM feeds
exist but route back through the same shop. We therefore split the pipeline:

- **Step 1 (manual, one-time, ~5 min):** open the two download-center URLs, drill down
  to Landkreis Darmstadt-Dieburg → Gemeinde Messel (and possibly Stadt Darmstadt if the
  bbox crosses the boundary), accept the free dl-de/zero-2.0 license, download the ZIPs.
  No login required.
- **Step 2+ (fully scripted):** unzip into `data/raw/dgm1/` and `data/raw/dop20/` and run
  the pipeline.

This is robust to future Intershop URL changes and keeps the licensing audit trail clean.

## Pipeline

```
data/raw/dgm1/*.tif          (29 DGM1 tiles — see data/tile_manifest.txt)
data/raw/dop20/*.jpg         (29 DOP20 tiles)
        │
        ▼  tools/prep_rasters.py
data/prep/dem.tif            (mosaicked, recentered to local origin, ~6000 × 9000 px @ 1 m)
data/prep/ortho.png          (mosaicked, RGB only, long axis capped at 16 384 px)
data/prep/origin.json        (original UTM SW corner + DEM stats)
        │
        ▼  src/messelpit/build_usd.py
out/messel.usd               (mesh + UV + UsdPreviewSurface with diffuse texture)
out/ortho.png                (copy of data/prep/ortho.png, referenced by the .usd)
out/messel.usdz              (zipped flavor for portable viewing)
```

### `tools/prep_rasters.py`

1. `rasterio.merge` all DGM1 GeoTIFFs → in-memory mosaic.
2. Crop to exact 3000 × 3000 m bbox (3000 × 3000 px at 1 m).
3. Translate origin so the SW corner is (0, 0) — Omniverse can't deal with raw UTM
   eastings/northings without precision loss. Record the original UTM SW corner in
   `data/prep/origin.json` for round-tripping.
4. Same crop on DOP20 → output as a JPEG-encoded PNG/PNG-compressed (drop the NIR band,
   keep RGB) at 1 m/px or 0.5 m/px (downsampled from 0.2 m to keep texture < 16 K).
5. Sanity check: print min/max elevation, mean slope, file sizes.

### `src/messelpit/build_usd.py`

1. Read `dem.tif` (3000 × 3000 float32) and `origin.json`.
2. Build a regular grid of vertices: x = col × 1.0, y = row × 1.0, z = dem[row, col].
   Skip / fill NoData (rare for Hessen DGM1).
3. Triangulate (two triangles per cell). Use `UsdGeomMesh` with `faceVertexCounts` /
   `faceVertexIndices` / `points`. Optionally use `subdivisionScheme = none`.
4. Generate UV coords matching the orthophoto: `st = (col / N, 1 - row / N)`.
5. Create a `UsdShadeMaterial` with `UsdPreviewSurface`:
   - `diffuseColor` ← `UsdUVTexture` reading `ortho.png` with the mesh's `st` primvar
   - `roughness = 0.9`, `metallic = 0.0`
6. Set stage `metersPerUnit = 1.0`, `upAxis = "Z"` (Omniverse default).
7. Save as `out/messel.usd` and pack to `out/messel.usdz`.

## Project layout

```
messelpit/
├── pyproject.toml          # uv-managed
├── README.md
├── CLAUDE.md
├── specs/messel-pit-usd.md # this file
├── tools/
│   ├── download_messel_data.py   # opens browser pages, prints checklist
│   ├── prep_rasters.py
│   └── verify_data.py            # sanity-check raw downloads
├── src/messelpit/
│   ├── __init__.py        # __version__
│   └── build_usd.py
├── data/
│   ├── tile_manifest.txt  # tracked: list of HVBG tile filenames the build expects
│   ├── raw/               # gitignored: dgm1/, dop20/ tiles unzipped from HVBG
│   └── prep/              # gitignored: dem.tif, ortho.png, origin.json
└── out/                   # gitignored
    ├── messel.usd
    ├── ortho.png
    └── messel.usdz
```

## Dependencies

- `rasterio` — read/crop/mosaic GeoTIFF
- `numpy` — array math
- `Pillow` — write the ortho PNG
- `usd-core` — author USD without a full Omniverse SDK install
- `rich` + `rich-argparse` — console UX (global preference)
- `requests` — open download pages (small helper only)

## Verifying in Omniverse

1. Open Omniverse Composer or USD Viewer.
2. File → Open `out/messel.usd`.
3. Frame the camera on `/World/Terrain`. Expect a 3 km × 3 km plate with the orthophoto
   draped; the Messel pit appears as a roughly 700 m wide, ~60 m deep oval depression
   near the center.

## Task status

| # | Task                                                    | Status   |
|---|---------------------------------------------------------|----------|
| 1 | Write this spec                                         | done     |
| 2 | Verify Hessen DGM1 / DOP20 distribution channels        | done     |
| 3 | Set up Python project (uv, pyproject.toml)              | pending  |
| 4 | `tools/download_messel_data.py` (open shop URLs)        | pending  |
| 5 | `tools/prep_rasters.py` (mosaic + crop + recenter)      | pending  |
| 6 | `src/messelpit/build_usd.py` (heightfield + texture)    | pending  |
| 7 | Document & smoke-test                                   | pending  |

## Open decisions

- **Texture resolution:** 0.2 m native over a 6 × 9 km area ⇒ 30 000 × 45 000 px raw,
  which busts the D3D12 16 384-per-axis cap. `prep_rasters.py --max-tex-dim 16384`
  (the default) scales the long axis down proportionally — current build produces
  **10 922 × 16 384** ortho.png (~0.55 m effective px).
- **Mesh density:** full 1 m grid over 6 × 9 km = ~54 M vertices, ~108 M triangles.
  This loads in Omniverse on a desktop GPU but is slow. Use `--decimate N` for
  iteration: `--decimate 2` → ~13.5 M verts, `--decimate 4` → ~3.4 M verts,
  `--decimate 8` → ~840 K verts (good for Quest streaming).
- **Coordinate origin:** SW corner of the cropped bbox is (0, 0, 0). Store original UTM
  in `origin.json` and as USD custom-data on the root prim so it round-trips.
