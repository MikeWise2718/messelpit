# CLAUDE_readme — Quick Reference for Claude Sessions

```
╔══════════════════════════════════════════════════════════════════╗
║  !! VERSION MANAGEMENT — READ BEFORE EVERY BUILD !!             ║
║                                                                  ║
║  Before rebuilding any USD file (messel.usd, messel_med.usd,   ║
║  etc.), ask Mike:                                                ║
║                                                                  ║
║  "Do you want me to save a versioned copy of the existing        ║
║   file before I overwrite it?"                                   ║
║                                                                  ║
║  Do this EVERY TIME without exception.                           ║
╚══════════════════════════════════════════════════════════════════╝
```

## "Open the project" / "Open in Omniverse"

Run this:

```powershell
Start-Process "C:\Messel_Project\messelpit_viewer\launch.bat" -WorkingDirectory "C:\Messel_Project\messelpit_viewer"
```

That's it. No searching, no drive-hunting.

## Key paths

| Thing | Path |
|---|---|
| This repo (pipeline) | `C:\Messel_Project\messelpit\` |
| Viewer repo | `C:\Messel_Project\messelpit_viewer\` |
| Viewer launcher | `C:\Messel_Project\messelpit_viewer\launch.bat` |
| USD output (default) | `C:\Messel_Project\messelpit\out\messel_med.usd` |

## Work protocol

Every session with Mike, maintain Protokoll_Emily.txt in the repo root.
Add a new timestamped line (YYYY-MM-DD) for each action or decision taken.
At the end of the session, commit the updated protocol to emily_branch.

## Git rules

- **NEVER suggest merging branches.** Ever. Don't offer it, don't ask about it.

## Vegetation troubleshooting workflow

All vegetation-related files live in `vegetation_troubleshooting/`:
- `ortho.png` — cropped colour orthophoto (auto-copied by prep_rasters.py)
- `veg_mask.png` — black/white vegetation mask (white = smooth DEM here)
- `make_veg_mask.py`, `smooth_dem.py` — copies of the tools for reference

Mask is edited manually in Krita: overlay ortho + mask, paint white over trees missed
by the auto-detection, export mask back to `vegetation_troubleshooting/veg_mask.png`.
Then run `uv run tools/smooth_dem.py` to produce `dem_smooth.tif`.
`build_usd.py` picks up `dem_smooth.tif` automatically.

Pit-only bbox (UTM 32N): `481700 5528400 483800 5530900` — use `--pit` shortcut or
`--bbox 481700 5528400 483800 5530900` with prep_rasters.py.

## Vegetation mask pipeline (current best practice)

Three signals combined via `tools/combine_veg_masks.py`:

1. **Height anomaly** (`--height-anomaly` flag in `make_veg_mask.py`) — compares
   each DEM pixel to a Gaussian-smoothed version. Pixels >N m above local average
   are canopy hits. Most accurate signal; no colour needed.
2. **Greenness index** (G-R)/(G+R) from ortho RGB — threshold ~0.08 (lower than
   original 0.15 to catch more). DOP20 has no NIR so NDVI is not available.
3. **Hand-painted mask** (`veg_mask_hp.png`) — manual corrections in Krita.

To regenerate the combined mask and rebuild USD:
```powershell
uv run tools/make_veg_mask.py          # writes veg_mask.png (greenness + height anomaly)
uv run tools/combine_veg_masks.py      # ORs veg_mask.png + veg_mask_hp.png → veg_mask_combined.png
uv run tools/smooth_dem.py -m vegetation_troubleshooting/veg_mask_combined.png
uv run src/messelpit/build_usd.py -d 4 -o out/messel_med.usd   # or -d 1 for full res
```

To open a specific USD in Omniverse (use MESSEL_USD env var):
```powershell
$env:MESSEL_USD = "C:\Messel_Project\messelpit\out\messel.usd"
Start-Process "C:\Messel_Project\messelpit_viewer\launch.bat" -WorkingDirectory "C:\Messel_Project\messelpit_viewer"
```

Full-res `messel.usd` (pit bbox, d=1, ~10.5M tris) is stable in Kit.
Old full-area `messel.usd` (~108M tris) crashes Kit after ~30s — do not use.

## Session recap — 2026-05-21

- Fixed CLAUDE.md sibling repo path (D:\senckenberg\ → C:\Messel_Project\)
- Created `tools/make_veg_mask.py` — generates B&W vegetation mask from DOP20 greenness index
- Created `tools/smooth_dem.py` — interpolates DEM under mask to remove canopy bumps
- Updated `tools/prep_rasters.py` with `--bbox` and `--pit` flags for pit-only crop
- Updated `src/messelpit/build_usd.py` to auto-use `dem_smooth.tif` if present
- Created `vegetation_troubleshooting/` folder with ortho, mask, and tool copies
- Final pit bbox: `481700 5528400 483800 5530900` (~2.1×2.5 km)
- DOP20 tiles are RGB only (no NIR) — mask uses greenness index as fallback
- Next step: user edits `veg_mask.png` in Krita, then runs `smooth_dem.py`
- All committed and pushed to `emily_branch` on GitHub

## Session recap — 2026-05-23

- Tested `veg_mask_hp.png` (hand-painted) through the full pipeline
- Added before/after Kit comparison via MESSEL_USD env var (two instances side-by-side)
- Created `tools/combine_veg_masks.py` — ORs auto + hand-painted masks; detects
  whether missed pixels are spectrally separable before adjusting threshold
- Found greenness alone gives only 18% coverage (no NIR, many trees spectrally
  ambiguous). Hand-painted missed pixels have median greenness 0.078 < threshold 0.15.
- Added height-anomaly detection to `make_veg_mask.py` — DEM bump detection is
  more accurate than colour for this dataset
- Rebuilt `messel.usd` (pit bbox, d=1, smoothed) — 10.5M tris, stable in Kit
- Full-area `messel.usd` (108M tris) confirmed to crash Kit as documented

## Notes

- The D: drive referenced in older docs does not exist on this machine. Both repos are under `C:\Messel_Project\`.
- `launch.bat` loads `messel_med.usd` via relative path — the two repos must stay siblings under `C:\Messel_Project\`.
