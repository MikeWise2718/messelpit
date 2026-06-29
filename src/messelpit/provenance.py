"""Neutral ``dt:`` provenance for the Messel scene.

The shared ``usd_viewer`` has a content-agnostic **"Sources" tab** (tab-kind
``provenance``) that reads a *neutral* ``dt:`` customData namespace off a
stage's ``/World`` prim — provider, license, and a computed OPEN/RESTRICTED
verdict — so any digital-twin pipeline lights it up by stamping the same keys.
The Kalahari project established the contract; this module is the Messel-side
implementation. See ``usd_viewer/specs/provenance-tab.md`` and
``specs/dt-provenance-stamping.md``.

Both Messel layers (DGM1 elevation, DOP20 imagery) are
*Datenlizenz Deutschland – Zero – 2.0* (open, redistributable), so the overall
tier computes to ``"open"`` (green badge).

The single entry point is :func:`stamp_dt_provenance(prim, origin_meta, ...)`,
called from both the terrain authoring (``build_usd.author_stage``) and the
overlay wrapper (``build_overlay_stage.author_wrapper``).
"""

from __future__ import annotations

from copy import deepcopy

from messelpit import __version__

_DLDE_ZERO = "Datenlizenz Deutschland – Zero – 2.0 (open, redistributable)"

# Messel's two base sources. CRS/datum confirmed against specs/messel-pit-usd.md
# (ETRS89 / UTM 32N, EPSG:25832, heights DHHN2016). Acquisition vintages are
# not yet recorded; left absent (stripped by _strip_nulls) until known.
ELEVATION = {
    "id": "dgm1",
    "kind": "dem",
    "provider": "Hessen DGM1 1 m LiDAR DTM (HVBG / Geobasis Hessen)",
    "license": _DLDE_ZERO,
    "tier": "open",
    "crs": "EPSG:25832",
    "datum": "ETRS89 / DHHN2016",
    "acquired": None,
}

TILEMAP = {
    "id": "dop20",
    "kind": "imagery",
    "provider": "Hessen DOP20 20 cm orthophoto (HVBG / Geobasis Hessen)",
    "license": _DLDE_ZERO,
    "tier": "open",
    "acquired": None,
}

# OpenStreetMap overlay (only stamped on wrappers that compose the OSM layer).
# Its presence is what lights up the viewer's "Open Street Maps" section.
OSM = {
    "id": "osm",
    "kind": "vector",
    "provider": "OpenStreetMap contributors",
    "license": "Open Database License (ODbL) 1.0",
    "tier": "open",
    "endpoint": "https://www.openstreetmap.org",
    "acquired": None,
}

# Most-restrictive tier wins (geometry carries the elevation license, so an
# open tilemap can't loosen a restricted DEM). All Messel sources are open.
_TIER_RANK = {"restricted": 2, "open": 1}


def compute_tier(*sources: dict) -> str:
    """Return the most-restrictive tier string across the given source tables.

    Unknown/absent tier on a source is treated as the most restrictive
    (fail-safe). Mirrors Kalahari's ``recipes.compute_tier``.
    """
    ranks = [_TIER_RANK.get(s.get("tier", "restricted"), 2) for s in sources]
    top = max(ranks) if ranks else 2
    for name, rank in _TIER_RANK.items():
        if rank == top:
            return name
    return "restricted"


def _strip_nulls(obj):
    """Recursively drop ``None`` leaves so the dict is USD-serializable.

    USD's ``VtValue`` has no mapping for Python ``None``; ``SetCustomDataByKey``
    raises on any null leaf. An absent key reads the same as "not applicable"
    downstream.
    """
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nulls(v) for v in obj if v is not None]
    return obj


def build_provenance(origin_meta: dict | None = None, *,
                     recipe: str = "messel-dop20",
                     include_osm: bool = False,
                     built_utc: str | None = None) -> dict:
    """Assemble the full ``dt:provenance`` lineage dict (nulls not yet stripped).

    ``include_osm`` adds the OSM source so the viewer's OSM section appears —
    set it on wrappers that compose ``messel_osm.usd``. ``tier`` is computed,
    never hand-set.
    """
    sources = [ELEVATION, TILEMAP] + ([OSM] if include_osm else [])
    # Copy the module-level source tables into the result so a caller mutating
    # the returned provenance (e.g. stamping an acquisition date) can't corrupt
    # the shared globals for the next build in the same process.
    prov = {
        "recipe": recipe,
        "tier": compute_tier(*sources),
        "elevation": deepcopy(ELEVATION),
        "tilemap": deepcopy(TILEMAP),
        "tool_version": __version__,
        "built_utc": built_utc,
    }
    if include_osm:
        prov["osm"] = deepcopy(OSM)
    if origin_meta is not None:
        prov["origin"] = origin_meta
    return prov


def stamp_dt_provenance(prim, origin_meta: dict | None = None, *,
                        recipe: str = "messel-dop20",
                        include_osm: bool = False,
                        built_utc: str | None = None) -> dict:
    """Stamp the neutral ``dt:`` provenance keys onto ``prim`` (a ``/World`` Usd.Prim).

    Authors ``dt:provenance`` (full lineage), ``dt:recipe``, ``dt:tier`` (the
    computed verdict), and ``dt:origin`` (convenience duplicate). Returns the
    cleaned provenance dict for logging/inspection.
    """
    prov = _strip_nulls(
        build_provenance(origin_meta, recipe=recipe,
                         include_osm=include_osm, built_utc=built_utc)
    )
    prim.SetCustomDataByKey("dt:provenance", prov)
    prim.SetCustomDataByKey("dt:recipe", prov.get("recipe", ""))
    prim.SetCustomDataByKey("dt:tier", prov.get("tier", "restricted"))
    if "origin" in prov:
        prim.SetCustomDataByKey("dt:origin", prov["origin"])
    return prov
