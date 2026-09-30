# Next steps

Where this scene can go from here, as of 2026-09-29. The working tracker is
`dthub/specs/dtlite.md`; this page is the readable summary.

## Geology: from schematic to data

| Step | What it needs | Effect |
|---|---|---|
| **Krister Smith's borehole model** ("Messel DT v0", GemPy, 811 boreholes, 195 picks of the oil shale's base) | an export from Krister (surfaces per unit or a lithology grid, plus the borehole table) | replaces the schematic bowl with a model built from boreholes; plan and open questions in `dthub/specs/messel-subsurface-model.md` |
| **Boreholes as a layer** | the same borehole table | 811 clickable columns showing collar, depth and picked contacts |
| **FB 2001's real position** | read off the 2003 Senckenberg site plan (`messel_karten/Position Lagerplatz Bohrklein .jpg`), fitted to the inclinometers it shows | the borehole column and the structural low in their surveyed place |
| **Harms' geological map** (1:25,000, with a cross-section through the pit) | georeference `messel_karten/MGKd_*.psd` | mapped outcrops and the published A–B section as a check on any model |
| **Nix Abb. 6** (NW–SE section with the mined-out sediments restored) | georeference the figure | a second published section to compare with the section cut |

## The pit through time

| Step | What it needs | Effect |
|---|---|---|
| **Past pit shapes** — 1937, 1957, 1960 | digitise the mine maps (archives of the former Bergamt Weilburg / Oberbergamt Wiesbaden) into surfaces | a time slider through the excavation |
| **1961–1997** | the aerial photo series (1961, 1967, 1971, 1977, 1985, 1986, 1993, 1997) | the later mining and back-filling stages |
| The **pre-mining ground** | already shown as the pale lid in the geology layer | — |

## Terrain and imagery

- **Flight dates** of the laser scan and the photos: look them up in HVBG's metadata
  records and add them to the source list.
- **Mark the no-data areas** instead of filling them, so the flat grey-green plains at the
  edges are no longer drawn.
- **Legacy survey** (the 2010-era `MESSEL.DXF` contours and spot heights, the Planquad
  excavation grid of Schaal & Müller 1991): already built for the Omniverse viewer; could
  become layers here too.

## Monitoring stations

- ~~Check IN23 against the printed table~~ — done 2026-09-30: the book itself prints
  116,18 (a misprint, probably for 160,18); see Monitoring stations.
- Find out **which stations still exist** and whether readings since 2003 are available —
  the 2001 heights against today's terrain already show where the ground has moved.

## Viewer

- **Try VR on the Quest** (HTTPS address, headset on the tailnet); tune the detail level
  for the headset.
- Raise **viewpoint heights with the exaggeration**, so prepared views stay above the
  stretched terrain.
- Re-drape roads **off the main thread** (a brief stutter when flying low).
- Keep **camera and layer choices per viewer** rather than per scene, so two people on
  two devices don't overwrite each other.

## Questions for Krister

1. Which export format suits his GemPy setup best?
2. Which colour is which unit in his section plot; are the shallow pockets at the rims
   the Upper Messel-Fm troughs?
3. Vertical datum, and which terrain model caps his model?
4. Is the triangle in his section FB 2001?
5. Does his model go below ~−150 m; may the FB 2001 log below it stay, marked schematic?
6. How should his work be credited in the viewer?
7. Does his database include the 2003 monitoring network?
