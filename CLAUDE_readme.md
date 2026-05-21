# CLAUDE_readme — Quick Reference for Claude Sessions

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

## Notes

- The D: drive referenced in older docs does not exist on this machine. Both repos are under `C:\Messel_Project\`.
- `launch.bat` loads `messel_med.usd` via relative path — the two repos must stay siblings under `C:\Messel_Project\`.
