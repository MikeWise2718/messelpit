"""Tests for prep_rasters._bbox_from_tile_names — filename -> UTM bbox.

prep_rasters lives under tools/ (not the installed package); pyproject's
pytest pythonpath adds tools/ so it imports by module name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prep_rasters import _bbox_from_tile_names


def _paths(*names):
    return [Path(n) for n in names]


def test_single_tile_bbox():
    # dgm1_32_482_5530_1_he.tif -> SW corner (482000, 5530000), 1 km tile.
    tiles = _paths("dgm1_32_482_5530_1_he.tif")
    assert _bbox_from_tile_names(tiles) == (482000, 5530000, 483000, 5531000)


def test_multi_tile_bbox_spans_extent():
    tiles = _paths(
        "dgm1_32_480_5526_1_he.tif",
        "dgm1_32_485_5534_1_he.tif",
        "dgm1_32_483_5530_1_he.tif",
    )
    # xmin/ymin from the SW-most, xmax/ymax = NE-most + 1 km.
    assert _bbox_from_tile_names(tiles) == (480000, 5526000, 486000, 5535000)


def test_dop20_naming_also_parses():
    # The regex keys on _32_<E>_<N>_ so DOP20 names parse the same way.
    tiles = _paths("dop20rgbi_32_482_5530_1_he.jpg")
    assert _bbox_from_tile_names(tiles) == (482000, 5530000, 483000, 5531000)


def test_unparseable_names_raise():
    tiles = _paths("README.txt", "notatile.tif")
    with pytest.raises(ValueError):
        _bbox_from_tile_names(tiles)


def test_unparseable_names_skipped_when_some_valid():
    tiles = _paths("garbage.tif", "dgm1_32_482_5530_1_he.tif")
    assert _bbox_from_tile_names(tiles) == (482000, 5530000, 483000, 5531000)
