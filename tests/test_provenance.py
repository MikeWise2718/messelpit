"""Tests for the neutral dt: provenance stamping (provenance.py).

Covers the tier algebra, null-stripping (USD can't serialize None), the
provenance dict shape the viewer's Sources tab reads, and the actual
customData round-trip on a real USD stage.
"""

from __future__ import annotations

from pxr import Usd, UsdGeom

from messelpit import __version__
from messelpit.provenance import (
    ELEVATION,
    OSM,
    TILEMAP,
    _strip_nulls,
    build_provenance,
    compute_tier,
    stamp_dt_provenance,
)


def test_messel_tier_is_open():
    # Both base sources are dl-de/zero-2.0 -> open.
    assert compute_tier(ELEVATION, TILEMAP) == "open"
    assert compute_tier(ELEVATION, TILEMAP, OSM) == "open"


def test_restricted_dominates_both_orderings():
    # Commutative: order of arguments must not change the verdict.
    assert compute_tier({"tier": "open"}, {"tier": "restricted"}) == "restricted"
    assert compute_tier({"tier": "restricted"}, {"tier": "open"}) == "restricted"


def test_unknown_tier_treated_as_restricted():
    # Fail-safe: a source with no tier counts as the most restrictive.
    assert compute_tier({"provider": "x"}, {"tier": "open"}) == "restricted"


def test_garbage_tier_string_treated_as_restricted():
    # An unrecognized tier value is not silently treated as open.
    assert compute_tier({"tier": "weird"}, {"tier": "open"}) == "restricted"


def test_no_sources_is_restricted():
    # Never claim "open" with nothing to back it.
    assert compute_tier() == "restricted"


def test_single_open_source():
    assert compute_tier({"tier": "open"}) == "open"


def test_strip_nulls_removes_none_leaves():
    obj = {"a": 1, "b": None, "c": {"d": None, "e": 2}, "f": [1, None, 3]}
    assert _strip_nulls(obj) == {"a": 1, "c": {"e": 2}, "f": [1, 3]}


def test_strip_nulls_keeps_falsey_non_none():
    # 0, "", False are valid values — only None is stripped. A naive `if v`
    # would wrongly drop these (the bug this guards against).
    src = {"zero": 0, "empty": "", "false": False, "none": None}
    assert _strip_nulls(src) == {"zero": 0, "empty": "", "false": False}


def test_build_provenance_does_not_mutate_module_globals():
    # The returned dict must be independent of the shared ELEVATION/TILEMAP/OSM
    # tables, so a caller editing it can't corrupt the next build in-process.
    prov = build_provenance(include_osm=True)
    prov["elevation"]["acquired"] = "2024-09-29"
    prov["tilemap"]["provider"] = "MUTATED"
    prov["osm"]["endpoint"] = "MUTATED"
    assert ELEVATION.get("acquired") is None
    assert TILEMAP["provider"].startswith("Hessen DOP20")
    assert OSM["endpoint"] == "https://www.openstreetmap.org"


def test_build_provenance_shape():
    prov = build_provenance({"epsg": 25832})
    assert prov["recipe"] == "messel-dop20"
    assert prov["tier"] == "open"
    assert prov["elevation"]["provider"].startswith("Hessen DGM1")
    assert prov["tilemap"]["provider"].startswith("Hessen DOP20")
    assert prov["tool_version"] == __version__
    assert prov["origin"] == {"epsg": 25832}
    # No OSM by default.
    assert "osm" not in prov


def test_build_provenance_with_osm():
    prov = build_provenance(include_osm=True)
    assert "osm" in prov
    assert prov["osm"]["endpoint"] == "https://www.openstreetmap.org"


def test_stamp_round_trips_on_stage(tmp_path):
    out = tmp_path / "s.usda"
    stage = Usd.Stage.CreateNew(str(out))
    world = UsdGeom.Xform.Define(stage, "/World")
    prim = world.GetPrim()

    stamp_dt_provenance(prim, {"epsg": 25832, "width_m": 6000}, include_osm=True)
    stage.GetRootLayer().Save()

    # Reopen and read exactly what the viewer reads.
    reopened = Usd.Stage.Open(str(out))
    w = reopened.GetPrimAtPath("/World")
    dt = w.GetCustomData().get("dt", {})
    assert dt.get("tier") == "open"
    prov = dt["provenance"]
    assert prov["elevation"]["provider"].startswith("Hessen DGM1")
    assert prov["tilemap"]["provider"].startswith("Hessen DOP20")
    assert "osm" in prov
    # dt:recipe / dt:origin convenience duplicates present.
    assert dt["recipe"] == "messel-dop20"
    assert dt["origin"]["epsg"] == 25832


def test_stamp_has_no_none_leaves(tmp_path):
    """The acquired=None fields must be stripped before stamping or USD raises."""
    out = tmp_path / "s.usda"
    stage = Usd.Stage.CreateNew(str(out))
    prim = UsdGeom.Xform.Define(stage, "/World").GetPrim()
    # Would raise "Invalid value type for customData" if a None leaked through.
    prov = stamp_dt_provenance(prim, None)
    assert "acquired" not in prov["elevation"]
