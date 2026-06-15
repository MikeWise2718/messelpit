# Legacy CAD + map overlays (messel_karten) — phased

Fold the **legacy 2010-era survey data** in `D:\senckenberg\messel_karten`
into the Messel USD scene as composable overlay layers, **one feature at a
time**, mirroring how the OSM data was added
(usd_viewer `specs/osm-overlay-and-visibility-tab.md`): pristine per-source
USD authored in messelpit + a thin wrapper that references them + a viewer
that's pure sidecar.

Status: **planning**. Each phase ships an end-to-end, viewable overlay
(authored → composed → toggleable in the viewer) before the next begins.
Nothing goes in all at once.

## Division of responsibility (two Claude projects)

This data spans **two repos with two CLAUDE.md files**. Keep the boundary
sharp — it's the same split OSM used, and the reason the viewer stays
content-agnostic.

| | **messelpit** (this repo) | **usd_viewer** (the consumer) |
|---|---|---|
| **Owns** | All **geo + USD authoring**. Reading the raw DXF/PSD, the coordinate transform, mesh/curve/material authoring, terrain knowledge, composition wrapper. | All **viewing + UI**. The Kit extension, the control-panel tabs, visibility toggling, per-scene persistence. |
| **Produces** | `out/messel_cad.usd`, `out/messel_maps.usd`, the `_with_overlays.usd` wrapper, converted textures. Pristine, frame-correct, defaultPrim `/World`. | Nothing authored into the USD. Reads the prim hierarchy + sidecar and renders toggles. |
| **Must NOT** | Know anything about the viewer's tabs, panel code, or Kit. | Contain any Messel/CAD/PSD-specific logic, hardcoded prim names, or geo code. Scene specifics live in the **sidecar**, not the extension. |
| **Interface** | The **prim hierarchy** (`/World/CAD/...`, `/World/Maps/...`) it authors, and the source `origin.json`. | The **sidecar JSON** (`<usd>.viewer.json`) that names those prim paths in a `visibility_list` tab. |
| **CLAUDE.md scope** | DXF/PSD parsing, projection, ezdxf, build CLIs. Where this spec lives. | Tab kinds, scene_state, panel rendering. A short pointer to this spec. |

The contract between them is exactly two things: **(1)** the agreed prim
paths under `/World/CAD` and `/World/Maps`, and **(2)** the sidecar that
references them. Neither side reaches across that line. When a phase
touches the viewer, the work is *only* sidecar edits unless a genuinely
new tab-kind capability is needed (none is — `visibility_list` already
ships).

## Source material triage

| File | What it really is | Phase |
|---|---|---|
| `MESSEL.DXF` (= `MESSEL3D.EXE` payload) | 2D contour + situation map: Höhenlinien 0.25/0.5/1.0/5.0 m (`HL_*`), flow arrows (`FLIES`), spot heights (`KOTE1`×528), facilities (`ANLAGEN`), labels (`TEXTE`). ~1 km, the pit. Misnamed "3D" (1 `3DFACE`). | **1** |
| `Planquad.psd` | 50 m **planquadrat grid** + contours; Senckenberg dig-recording reference (Schaal & Müller 1991, CFS 139:127-145) | **2** |
| `dgm_messel.dxf` (114 MB) | Denser contours: `HL_*M` 0.5/1.0/5.0 m + spot heights (`KOTEN`×527). Not a mesh. Likely redundant with LiDAR. | **3** |
| `MGKd_{L,M,O,P}__.psd` | One map, 4 res tiers (CMYK); P = 7320×10391 | **3** |
| `MESSEL3D.DWG`, `MESSEL3D.dxf`, `messel3d.dgn` | Same survey, other formats | — (duplicates) |
| `Messel.psd`, `Position Lagerplatz Bohrklein.jpg` | Another map; drill-cuttings-storage photo | **4** (deferred, low value) |
| `*.EXE` (LHa SFX), `Thumbs.db`, `__tmp.*`, `Liesmic2.doc`, `Mime.822`/`.rtf` | Self-extractors (payloads on disk), junk, HiCAD temp, readme, emails | — (not scene data; emails+doc = provenance) |

## Coordinate finding (shared by all phases — verified against the DEM)

DXF coords are **UTM 32N (EPSG:25832)**, same datum/projection as the
LiDAR pipeline, so **no reprojection** — only a translation. Easting is
raw UTM; northing is truncated (5_5xx_xxx printed as 5xx_xxx):

```
local_x = E_dxf                  - 480000
local_y = (N_dxf + 4_998_232)    - 5_526_000
local_z = Z_dxf                                  # meters MSL, as-is
```

⚠️ **Correction (Phase 1 build):** the northing restore is **+4_998_232**,
NOT the clean +5_000_000 first guessed. +5e6 looked right because a single
point still landed *somewhere on the Messel map sheet* — but it put the
geometry **~1.8 km too far north** of the actual pit (visible in the
viewer as contours scattered in the forest). The correct value was derived
by **aligning the DXF's pit-floor spot heights (lowest `KOTE1` elevations)
to the LiDAR DEM pit floor** (cells below 122 m in `data/prep/dem.tif`);
alignment error after fix: 0 m N, 64 m E (within centroid noise). Lesson:
verify placement against the *pit*, not just "is it on the sheet."

The constant lives in `build_cad_overlay.py` (`NORTHING_RESTORE`) and is
overridable with `--northing-restore` for other sheets. **Each phase that
ingests a file asserts** its transformed bbox lands inside the DEM bbox
(0..6000 × 0..9000) and fails loudly otherwise.

---

## Phase 1 — MESSEL.DXF contours (the foundation)

**Goal:** the surveyed pit contours + spot heights, toggleable in a new
"Survey" tab. This is first because it's high value *and* its on-terrain
geometry becomes the visual reference Phase 2 georeferences against.

### messelpit (authoring)
- Add `ezdxf` to `pyproject.toml` (proper DXF parser — do NOT hand-scan
  group codes; the analysis-phase quick scan was unreliable).
- New `src/messelpit/build_cad_overlay.py`:
  - Parse `MESSEL.DXF` with ezdxf; translate every vertex to local frame.
  - Assert bbox ⊂ DEM bbox.
  - Contours (`HL_*` POLYLINE, Z per vertex — already draped, the lines
    ARE the surface) → **flat ribbon `UsdGeom.Mesh`** grouped by interval:
    `/World/CAD/Survey/Contours/{c025,c05,c10,c50}`.
  - Spot heights (`KOTE1` INSERTs) → **flat square marker `UsdGeom.Mesh`**
    `/World/CAD/Survey/SpotHeights`.
  - Facilities (`ANLAGEN`) → ribbon mesh `/World/CAD/Survey/Facilities`.
    (`TEXTE` labels, flow arrows: Phase 4.)
  - Per-group emissive `UsdPreviewSurface`, legible colors (faint 0.25 m →
    bold 5 m). RTX needs a real surface shader (lion-enclosure lesson).
  - CLI (uv/rich/rich-argparse, short flags): `python -m
    messelpit.build_cad_overlay -i <MESSEL.DXF> -o out/messel_cad.usd`.

  ⚠️ **Geometry-type correction (Phase 1 build):** contours/spot-heights
  were first authored as `BasisCurves` / `Points`, but **RTX silently
  drops both** (they never rendered, while the OSM building *meshes* did).
  Switched to **meshes** — flat horizontal ribbons per polyline, flat
  square markers per spot height — the same call the OSM builder made for
  roads. Per-interval ribbon width is configurable (`--width-c025/05/10/50`,
  or `--contour-width` for all); spot-marker size `--spot-width`; both
  lifted `--z-lift` (default 1 m) above terrain to avoid z-fighting.
  Tuned defaults: widths c025=1.5 / c05=2 / c10=2.5 / c50=4 m, markers 6 m.
- Extend `build_overlay_stage.py` to optionally reference `messel_cad.usd`
  under `/World/CAD` → new wrapper `out/messel_lo_with_overlays.usd` (keep
  `_with_osm` working). No transform — shared frame.

### usd_viewer (consumer)
- **New separate tab** (not folded into OSM's "Overlays"): a second
  `visibility_list` tab named **"Survey"** in the sidecar
  `data/messel_lo_with_overlays.usd.viewer.json`, groups pointing at
  `/World/CAD/Survey/...`. Default **off** via scene_state so the scene
  opens clean.
- Copy fresh `out/messel_*` into `usd_viewer/data/`.
- **No extension code** — `visibility_list` kind, renderer,
  `set_prim_visible`, persistence all shipped with OSM.

### Done when — ✅ LOCKED (2026-06-15)
Open `messel_lo_with_overlays.usd` in the viewer → a **"Survey" tab**
appears next to "Overlays" → toggling shows/hides contour ribbons + spot
markers that sit **on the pit** (verified in-Kit, desktop). Geometry
renders (mesh, not curves), is correctly placed (DEM-aligned offset), and
per-interval widths are tunable. Remaining nice-to-haves pushed to a
later polish pass: VR visual check; flat markers/ribbons poke through
steep pit walls (could drape per-vertex or set z-lift 0); pick final
default widths once a preferred look is chosen.

---

## Phase 2 — Planquad.psd excavation grid (draped image)

**Goal:** the 50 m planquadrat grid draped on the terrain, toggleable in
the same "Survey" tab. Depends on Phase 1 for georef verification.

### messelpit (authoring)
- PSD → RGBA: `Planquad` is 1-bit; threshold to lines-on-transparent (no
  white box). (Pillow/`psd-tools`.)
- Georef corners **derived from the MESSEL.DXF local-frame bbox** (your
  decision) — the DXF authored in Phase 1 gives a verified extent.
- Author a draped textured quad (`UsdGeom.Mesh`, DEM-sampled vertices or
  a slight z-offset) `/World/Maps/Planquad`, `UsdPreviewSurface` texture.
- Output `out/messel_maps.usd`; extend the wrapper to also ref it under
  `/World/Maps`.

### usd_viewer (consumer)
- Add a "Excavation grid (Planquad)" group to the **"Survey" tab** sidecar,
  pointing at `/World/Maps/Planquad`. Default off.
- Copy artifacts; in-viewer **alignment QA** against the Phase-1 contours.

### Done when
Toggling "Excavation grid" drapes the 50 m grid onto the terrain, aligned
with the Phase-1 contours. If misaligned: affine-fit fallback on 2 known
grid intersections (note in tracker).

---

## Phase 3 — secondary layers (dgm contours + MGKd sheet)

Only after 1–2 prove the pattern. Each is an independent toggle so it
earns its place or gets dropped.

- **messelpit:** parse `dgm_messel.dxf` → `/World/CAD/ContoursDGM/{c05,c10,c50}`
  (reuse the Phase-1 builder, `-df` flag). Convert `MGKd_P__.psd`
  (CMYK→RGB) → `/World/Maps/MGKd` draped quad.
- **usd_viewer:** two more groups in the "Survey" tab sidecar, both
  default off.

---

## Phase 4 — polish (deferred)

- **messelpit:** `TEXTE` labels + billboard spot-height numbers; flow-
  direction arrows; `Messel.psd` / drill-storage marker.
- **usd_viewer:** any label-toggle group if labels land.
- Record provenance (the 2010 email thread, Schaal & Müller citation) in a
  scene "About"/info group if useful.

---

## Task tracker

| # | Task | Phase | Repo | Status |
|---|------|------|------|--------|
| 1 | This phased spec + responsibility split | — | messelpit | ✅ |
| 2 | Confirm coord offset empirically | — | messelpit | ✅ (8.760E/49.935N) |
| 3 | Add `ezdxf` dep | 1 | messelpit | ✅ (ezdxf 1.4.4, pyproject) |
| 4 | `build_cad_overlay.py`: parse MESSEL.DXF + local-frame translate + bbox assert | 1 | messelpit | ✅ DEM-aligned northing +4_998_232; bbox inside DEM |
| 5 | Contours → grouped by interval, per-group material | 1 | messelpit | ✅ ribbon **meshes** (curves dropped by RTX); c025/c05/c10/c50, 2228 lines |
| 6 | Spot heights → markers; facilities | 1 | messelpit | ✅ 528 square marker meshes; 3 ANLAGEN ribbons |
| 7 | CLI (uv/rich/rich-argparse, short flags) → out/messel_cad.usd | 1 | messelpit | ✅ `-i/-o/-p`, per-interval `-w025/05/10/50`, `-sw/-zl/-nr`; 89 garbage dropped |
| 8 | Extend build_overlay_stage.py: ref CAD under /World/CAD → _with_overlays.usd | 1 | messelpit | ✅ `--overlay/--cad/--maps`; composed stage validated |
| 9 | NEW "Survey" visibility_list tab in sidecar; default off | 1 | usd_viewer | ✅ 2 tabs load (Overlays 18, Survey 7); + `run_messel_overlays.bat` |
| 10 | Copy artifacts to data/; in-viewer QA (contours on terrain) | 1 | usd_viewer | ✅ in-Kit verified on pit (desktop); VR check deferred to polish |
| 11 | Planquad PSD → RGBA transparent-grid texture | 2 | messelpit | ☐ |
| 12 | Draped Planquad quad from DXF-derived corners → messel_maps.usd; ref under /World/Maps | 2 | messelpit | ☐ |
| 13 | Add Planquad group to Survey tab sidecar | 2 | usd_viewer | ☐ |
| 14 | Alignment QA vs Phase-1 contours; affine-fit fallback if off | 2 | usd_viewer | ☐ |
| 15 | dgm_messel.dxf → /World/CAD/ContoursDGM (reuse builder, -df) | 3 | messelpit | ☐ |
| 16 | MGKd_P PSD (CMYK→RGB) draped → /World/Maps/MGKd | 3 | messelpit | ☐ |
| 17 | Two more Survey-tab groups (DGM contours, MGKd) | 3 | usd_viewer | ☐ |
| 18 | TEXTE labels, billboard spot heights, flow arrows, Messel.psd, provenance | 4 | both | ☐ |

## Open questions (resolve at impl time)

- **PSD corner accuracy** (Phase 2): DXF-derived bbox assumes no map
  margin border; QA against contours, affine-fit fallback.
- **`dgm_messel.dxf` value** (Phase 3): likely redundant with LiDAR — its
  own toggle so it justifies inclusion or is dropped.
- **Contour geometry:** BasisCurves (clean lines) vs thin ribbons
  (RTX/VR robustness, per OSM road decision). Leaning BasisCurves.
- **Wrapper naming:** new `messel_lo_with_overlays.usd` vs extend
  `_with_osm`. Leaning new name, keep old for back-compat.

## References

- OSM precedent (the pattern this mirrors, incl. the same repo split):
  usd_viewer `specs/osm-overlay-and-visibility-tab.md`
- Coordinate truth: `data/prep/origin.json` (SW origin 480000/5526000)
- Existing wrapper authoring: `src/messelpit/build_overlay_stage.py`
- Source + provenance: `D:\senckenberg\messel_karten` (`Mime.822` email
  thread; `Liesmic2.doc` = Planquad readme, Schaal & Müller 1991)
- ezdxf: <https://ezdxf.readthedocs.io/>
