# Grube Messel — overview

**Start here if you have never seen this scene.**

## What this place is

Grube Messel is a former **oil-shale open-pit mine** near Darmstadt (Hesse, Germany),
now a **UNESCO World Heritage fossil site** (listed 1995) run by Senckenberg (trustee
since 1992). The pit cuts into the sediments of a **maar lake** — a crater lake that
formed after a volcanic eruption about **48 million years ago** (Eocene). Its finely
layered oil shale preserved plants and animals in extraordinary detail.

Industrial mining ran from **1885 to 1971** and left a bowl about **60–70 m deep**: the
pit floor is at ~104 m above sea level, the rims at 160–170 m. The slopes have kept
moving ever since, which is why the pit is monitored (see
[Monitoring stations](04-monitoring-stations.md)).

## What you are looking at

The scene is a **6 × 9 km** block around the pit (north is up at the start). Messel
village is north of the pit, the Darmstadt–Dieburg railway runs along its north rim.

| You see | What it is | Real or schematic? | More |
|---|---|---|---|
| The ground | 1 m laser-scanned terrain (HVBG DGM1) | real (measured) | [Terrain & imagery](02-terrain-and-imagery.md) |
| The colours on it | aerial photographs (HVBG DOP20) | real | [Terrain & imagery](02-terrain-and-imagery.md) |
| **Flat grey-green areas** at the edges | **no data** — outside the map tiles we downloaded | filler | [Terrain & imagery](02-terrain-and-imagery.md) |
| Roads and buildings | OpenStreetMap, draped on the terrain | real (crowd-mapped) | [OSM layer](03-osm.md) |
| Coloured pins in the pit | 171 slope-monitoring stations from a 2003 study | real positions | [Monitoring stations](04-monitoring-stations.md) |
| Coloured sheets under the ground (Geology, off at start) | the rock layers of the maar | **schematic** | [Geology](05-geology.md) |
| A striped column in the pit centre | the 433 m research borehole FB 2001 | real depths, **assumed** position | [Geology](05-geology.md) |

What is known and what is assumed is collected in one place:
[Assumptions & unknowns](06-assumptions.md).

## A two-minute tour

1. Press **Pit Rim** in the header: you stand on the north rim looking into the pit.
2. Set **Exaggeration** to 3×: the terraced slopes (the old mining benches) and the
   slide scarps stand out.
3. Tick **Geology** in the layer panel: the ground fades and the layers under the pit
   appear — oil shale on top, the older lake sediments below, the volcanic pipe deepest.
4. Tick **Section** in the header: the near half is cut away and the cut face shows
   the layers like a textbook cross-section. Drag the direction slider to turn it.
5. Click anything — a pin, a road, a layer — to see what it is and where it came from.

## Who

Built by Mike Wise (Senckenberg volunteer) with **Krister Smith** (Senckenberg, Messel).
The scene data is produced by the `messelpit` repo; the viewer is `dtlite`. Versions,
build dates and the full source list are in **About**.
