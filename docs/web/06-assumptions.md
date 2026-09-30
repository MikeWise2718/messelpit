# Assumptions & unknowns

Everything in this scene that is **not** straight measurement, in one list. When one of
these is resolved, fix the data and strike it here.

## Terrain and imagery

- **Flight dates unknown** for both the laser scan (DGM1) and the photos (DOP20).
- **~46 % of the scene is filler**: no tile was downloaded there, and the gaps were
  filled with the nearest measured height (flat plains) and grey imagery.
- Imagery shown at ~0.55 m per pixel (resampled), not the 20 cm original.

## OSM

- Building heights: almost all are the **6 m default** (OSM records few heights).
- OSM is a snapshot of **2026-06-13**; it is crowd-mapped, not surveyed.

## Monitoring stations

- Coordinates were **OCR'd** from a scanned table and cleaned by hand; the datum shift
  from Gauss–Krüger is the standard one (≈1 m). Checked: 97 % of heights match today's
  terrain within 2 m.
- **IN23**'s height is 43.9 m off: a misprint in Nix (checked against the scan), most
  likely 160,18 printed as 116,18. Kept as printed, flagged.
- They are the **2001–2003** network; which stations still exist today is not known.

## Geology — schematic

- The **outline** is an ellipse fitted to today's pit, not the mapped deposit boundary.
- The **bowl shape**, the **22.5° rim dip**, the **60° crater walls** and the **pipe
  widths** are invented to fit six published numbers.
- **FB 2001's position** is assumed (the lowest point of today's pit floor); the 2003
  site plan in `messel_karten` shows the real one.
- Unit thicknesses away from FB 2001 are FB 2001's.
- Krister Smith's borehole model suggests the real shape differs (a narrow deep
  trough, a north–south deposit) — see [Geology](05-geology.md).
- The **pre-mining ground** (168 m) is a flat estimate: oil-shale top ~166 m + 1–3 m of
  younger cover.
