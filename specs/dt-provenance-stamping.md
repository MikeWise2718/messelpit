# Stamp neutral `dt:` provenance so the Messel scene gets a "Sources" tab

## Why

The shared `usd_viewer` has a generic **"Sources" scene-tab** (tab-kind
`provenance`) that shows a scene's data lineage (elevation source, map-tile source,
licenses, and an overall RESTRICTED/OPEN badge). It is **scene-agnostic**: it reads a
*neutral* `dt:` customData namespace off the stage's `/World` prim, so any digital-twin
pipeline can light it up by stamping the same keys.

The **Kalahari** project (`D:\senckenberg\Kalihari_dt`) already stamps `dt:` provenance,
so its scenes show a Sources tab. **Messel does not** — `messelpit` stamps the older,
project-specific `messelpit:` keys (`messelpit:version`, `messelpit:origin`), which the
generic tab doesn't read. So even if a Messel sidecar declared the tab, it would render
empty / fall back.

This spec describes the change to make on the **messelpit side** so the Messel scene
shows a Sources tab too, consistent with Kalahari. (We keep this work in `messelpit`
rather than mutating the built USD from another repo, to respect the repo boundary:
`messelpit` owns its USD authoring.)

## The contract (what the viewer reads)

The viewer reads these off `/World` customData (see
`usd_viewer/specs/provenance-tab.md`). USD `:` nests keys under a `dt` dict, so
`SetCustomDataByKey("dt:tier", ...)` is read back as `customData["dt"]["tier"]`.

```
/World customData:
  dt:tier        = "open" | "restricted"     # computed overall verdict (most-restrictive wins)
  dt:recipe      = "<human label>"           # optional, e.g. "messel-dop20"
  dt:origin      = { ... }                    # convenience duplicate of provenance.origin
  dt:provenance  = {                          # the full lineage
      recipe    = "<label>",
      tier      = "open" | "restricted",
      elevation = { provider, kind, license, tier, crs?, datum?, acquired?, path? },
      tilemap   = { provider, kind, license, tier, acquired?, ... },
      origin    = { ... },                    # the existing messelpit origin_meta is fine here
      built_utc = "<iso>",                    # optional
      tool_version = "<x.y.z>",               # optional
  }
```

`tier` is **computed**, never hand-set: take the most-restrictive tier across the
sources. For Messel both sources are open (see below), so `tier = "open"`.

## Messel's actual sources (from `specs/messel-pit-usd.md`)

Both layers are **Datenlizenz Deutschland – Zero – Version 2.0** (open, no attribution
required, redistributable) → overall **`tier = "open"`** (green badge).

- **Elevation — DGM1**: Hessen state 1 m LiDAR digital terrain model (HVBG / Geobasis
  Hessen). 29 tiles (1 km × 1 km). License: dl-de/zero-2.0.
- **Imagery — DOP20**: Hessen 20 cm digital orthophoto (HVBG / Geobasis Hessen).
  License: dl-de/zero-2.0.

Suggested concrete values:

```python
elevation = {
    "id": "dgm1",
    "kind": "dem",
    "provider": "Hessen DGM1 1 m LiDAR DTM (HVBG / Geobasis Hessen)",
    "license": "Datenlizenz Deutschland – Zero – 2.0 (open, redistributable)",
    "tier": "open",
    "crs": "EPSG:25832",          # confirm against the actual DGM1 tiles (UTM32N)
    "datum": "ETRS89",
    # "acquired": "<vintage if known>",
}
tilemap = {
    "id": "dop20",
    "kind": "imagery",
    "provider": "Hessen DOP20 20 cm orthophoto (HVBG / Geobasis Hessen)",
    "license": "Datenlizenz Deutschland – Zero – 2.0 (open, redistributable)",
    "tier": "open",
    # "acquired": "<flight date if known>",
}
```

## Implementation (messelpit side)

The terrain stage is authored in `src/messelpit/build_usd.py:author_stage()`, which
today stamps (around lines 80–81):

```python
world.GetPrim().SetCustomDataByKey("messelpit:version", __version__)
world.GetPrim().SetCustomDataByKey("messelpit:origin", origin_meta)
```

### 1. Add the `dt:` stamps alongside the existing `messelpit:` ones

Keep `messelpit:` for backward compatibility; **add** the neutral keys:

```python
prim = world.GetPrim()
# existing:
prim.SetCustomDataByKey("messelpit:version", __version__)
prim.SetCustomDataByKey("messelpit:origin", origin_meta)

# NEW — neutral dt: provenance for the viewer's generic "Sources" tab.
ELEVATION = { ... }   # the dict above
TILEMAP   = { ... }   # the dict above
tier = _compute_tier(ELEVATION, TILEMAP)   # most-restrictive; here "open"
provenance = {
    "recipe": "messel-dop20",
    "tier": tier,
    "elevation": ELEVATION,
    "tilemap": TILEMAP,
    "origin": origin_meta,
    "tool_version": __version__,
    # "built_utc": <iso>,   # optional; pass in like Kalahari does
}
provenance = _strip_nulls(provenance)      # USD VtValue can't serialize None
prim.SetCustomDataByKey("dt:provenance", provenance)
prim.SetCustomDataByKey("dt:recipe", provenance["recipe"])
prim.SetCustomDataByKey("dt:tier", provenance["tier"])
prim.SetCustomDataByKey("dt:origin", origin_meta)
```

Helpers (copy the pattern from `Kalihari_dt/tools/recipes.py` and
`Kalihari_dt/tools/build_usd.py`):

```python
_TIER_RANK = {"restricted": 2, "open": 1}
def _compute_tier(*sources):
    top = max((_TIER_RANK.get(s.get("tier", "restricted"), 2) for s in sources), default=2)
    return next(n for n, r in _TIER_RANK.items() if r == top)

def _strip_nulls(obj):
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nulls(v) for v in obj if v is not None]
    return obj
```

> **Gotcha (learned on Kalahari):** `SetCustomDataByKey` raises
> `Invalid value type for customData...` on any Python `None` leaf — always run the
> provenance dict through `_strip_nulls` first.

### 2. Apply to the overlay/wrapper stages too (optional but tidy)

`build_overlay_stage.py` composes `messel_lo.usd` (+ OSM) under a wrapper `/World`. The
viewer reads `/World` customData of the **opened** stage. If users open
`messel_lo_with_osm.usd` (the wrapper), the wrapper's `/World` needs the `dt:` keys too —
either author them on the wrapper, or rely on composition surfacing the sublayer's
customData (verify which; wrapper-authored is safest). Bump `__version__`.

### 3. Rebuild + refresh the viewer copy

```
# in messelpit
uv run tools/build_variants.ps1      # or however messel_lo.usd is built
```
Then copy the rebuilt `messel_lo.usd` (and the wrapper if used) into the viewer's
`usd_viewer/data/messel/` (the viewer keeps its own gitignored copy of the heavy USD;
only the sidecar JSON is tracked there).

## usd_viewer side (one-line sidecar edit — can be done now, independent of messelpit)

Add the tab to the Messel sidecar(s) so it appears once the USD carries `dt:`:

`usd_viewer/data/messel/messel_lo_with_osm.usd.viewer.json` — add to `scene_tabs`:
```json
{ "name": "Sources", "kind": "provenance", "restrictions_tab": true, "restrictions_name": "Restrictions" }
```
The viewer ignores a declared `provenance` tab gracefully if the stage has no
`dt:provenance` yet (renders empty / falls back), so declaring it early is safe.

## Verify

```python
from pxr import Usd
s = Usd.Stage.Open("data/messel/messel_lo.usd")
dt = s.GetPrimAtPath("/World").GetCustomData().get("dt", {})
assert dt.get("tier") == "open"
assert dt["provenance"]["elevation"]["provider"].startswith("Hessen DGM1")
```
Then open the scene in usd_viewer → a **Sources** tab should show Elevation (DGM1) +
Map Tiles (DOP20) + an **OPEN** (green) badge, with a Restrictions sub-tab.

## Task status

| Step | Owner | Status |
|------|-------|--------|
| Confirm DGM1 CRS/datum + acquisition vintages for accurate fields | messelpit | ◑ CRS/datum confirmed (EPSG:25832 / ETRS89 / DHHN2016); vintages still unknown (`acquired` omitted, stripped by `_strip_nulls`) |
| Add `dt:` stamps + `compute_tier`/`_strip_nulls` in `build_usd.py` | messelpit | ✅ in new `provenance.py` (`stamp_dt_provenance`), called from `author_stage` |
| Handle wrapper/overlay stages (`build_overlay_stage.py`) | messelpit | ✅ wrapper re-stamps `dt:` on its own `/World`; `include_osm` lights the OSM section |
| Bump `__version__`, rebuild `messel_lo.usd` | messelpit | ✅ 0.1.0 → 0.2.0; rebuilt lo + med + both wrappers |
| Copy rebuilt USD into `usd_viewer/data/messel/` | messelpit → viewer | ✅ lo + both wrappers copied; `dt:` verified in viewer copy |
| Add `Sources` tab to Messel sidecar(s) | usd_viewer | ✅ added to both `messel_lo_with_osm` + `messel_lo_with_overlays` sidecars |
| Verify tab renders with OPEN badge | — | ◑ contract verified programmatically (tier=open, OSM section on); **in-Kit visual check pending user** |

**Notes from implementation:**
- Helpers live in a dedicated `src/messelpit/provenance.py` (not inline in
  `build_usd.py`) since both the terrain build and the wrapper need them.
- `build_provenance` **deep-copies** the module-level source tables into the
  result (Kalahari pattern) so a caller editing the returned provenance can't
  corrupt the shared globals for the next build in-process. Covered by
  `tests/test_provenance.py::test_build_provenance_does_not_mutate_module_globals`.
- The wrapper authors its **own** `dt:` opinion rather than relying on the
  referenced base's customData composing through — safest per the spec.
- Sidecar uses the refined single-tab form `{ "name": "Sources", "kind":
  "provenance" }`; the legacy `restrictions_tab`/`restrictions_name` keys the
  original draft suggested are now ignored by the viewer (v0.9.3).

## References

- Viewer contract: `D:\senckenberg\usd_viewer\specs\provenance-tab.md`
- Working reference implementation: `D:\senckenberg\Kalihari_dt\tools\build_usd.py`
  (`author_stage`, `_strip_nulls`) and `tools\recipes.py` (`compute_tier`, `provenance`)
- Messel sources/licenses: `specs\messel-pit-usd.md` (§ Data sources)
