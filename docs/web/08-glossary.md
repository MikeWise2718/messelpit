# Glossary

The abbreviations used in these pages and in the viewer, grouped by topic. German terms
are given with a translation.

## Maps and survey data

| Term | Stands for | Meaning here |
|---|---|---|
| **DGM1** | *Digitales Geländemodell*, 1 m | Digital terrain model: the bare ground (buildings and trees removed) on a 1 m grid, from airborne laser scanning. Messel's terrain. |
| **DOP20** | *Digitale Orthophotos*, 20 cm | Aerial photos corrected for terrain and camera tilt, so every pixel is in its true map position; 20 cm per pixel. Messel's colours. |
| **DEM** | Digital elevation model | The general term for a height grid; DGM1 is one. |
| **HVBG** | *Hessische Verwaltung für Bodenmanagement und Geoinformation* | Hesse's state survey office; source of DGM1 and DOP20. |
| **HLUG** | *Hessisches Landesamt für Umwelt und Geologie* | Hesse's former geological survey (now HLNUG); publisher of Nix (2003). |
| **OSM** | OpenStreetMap | The crowd-mapped world map; source of the roads and buildings. |
| **NIR** | Near infrared | A fourth band in the aerial photos; dropped, only red/green/blue are shown. |
| **RGB** | Red, green, blue | The three colour bands of an image. |
| **GPS** | Global Positioning System | Satellite positioning; used for the temporary survey points. |
| **OCR** | Optical character recognition | Reading text from a scanned page; how the station table was taken from Nix (2003). |
| **DXF** | Drawing Exchange Format | AutoCAD's exchange format; the 2010-era `MESSEL.DXF` survey drawing. |
| **GeoTIFF** | — | A TIFF image carrying its map position; the format of the terrain files. |

## Coordinates and heights

| Term | Stands for | Meaning here |
|---|---|---|
| **UTM** | Universal Transverse Mercator | A worldwide grid of 60 zones, positions in metres (easting, northing). Messel lies in **zone 32N**. |
| **ETRS89** | European Terrestrial Reference System 1989 | The European reference frame the modern German data uses. |
| **EPSG** | European Petroleum Survey Group | Keeper of the registry of numbered coordinate systems: **EPSG:25832** = ETRS89 / UTM 32N (today's data), **EPSG:31467** = DHDN / Gauss-Krüger zone 3 (the 2001 survey). |
| **DHDN** | *Deutsches Hauptdreiecksnetz* | The older German reference frame, used until the 2010s. |
| **GK3** | Gauss-Krüger zone 3 | The older German map grid on DHDN; the monitoring stations were surveyed in it and are converted to UTM for the viewer. |
| **DHHN2016** | *Deutsches Haupthöhennetz 2016* | Germany's current height system; heights in metres above sea level. |
| **m NN** | Metres above *Normalnull* | The older German sea-level datum; how Nix (2003) gives heights. Close enough to DHHN2016 to compare directly here: the 2001 station heights match today's DGM1 to a median of 3 cm. |
| **SW, SE, NW** | South-west, south-east, north-west | Compass directions; the scene's origin is its **SW** corner. |

## Geology and the monitoring network

| Term | Stands for | Meaning here |
|---|---|---|
| **FB 2001** | *Forschungsbohrung* 2001 | The 433 m research borehole in the pit, drilled in 2001; the striped column. |
| **Fm** | Formation | A named rock unit, e.g. *Messel-Fm* (the lake sediments). |
| **Abb.** | *Abbildung* | "Figure" in a German publication, e.g. Nix Abb. 6 (a cross-section). |
| **Geol. Abh.** | *Geologische Abhandlungen* | "Geological Treatises", the Hessian survey's series that published Nix (2003). |
| **pp.** | pages | Page count of a publication. |
| **IN** | inclinometer | Station prefix: IN 1–28, tubes that measure the ground sliding sideways. |
| **KP** | piezometer (our reading: *Kontrollpegel*, monitoring gauge) | Station prefix: KP 101–525, shallow groundwater levels. Nix does not spell the letters out. |
| **GW** | deep well (our reading: *Grundwasser*, groundwater) | Station prefix: GW 1–5, groundwater in the crystalline rock. Nix does not spell the letters out. |
| **F** | fixed geodetic point (*Festpunkt*) | Station prefix: F1–F5, survey reference points. |
| **IN23** | inclinometer no. 23 | The station whose printed height looks misread (see Assumptions). |
| **GemPy** | — | Open-source software for 3D geological models from boreholes; what Krister Smith's "Messel DT v0" is built in. |
| **DT** | Digital twin | A detailed computer model of a real place, kept in step with data about it. |
| **UNESCO** | United Nations Educational, Scientific and Cultural Organization | Lists Messel as a World Heritage site (1995). |

## The software

| Term | Stands for | Meaning here |
|---|---|---|
| **dtlite** | "digital twin lite" | This viewer: the browser version. |
| **USD** | Universal Scene Description | Pixar's 3D scene format; what the full Omniverse viewer (usd_viewer) reads. |
| **RTX** | — | NVIDIA's ray-tracing graphics cards and renderer, used by the Omniverse viewer. |
| **VR** | Virtual reality | Viewing the scene in a headset (Meta **Quest**). |
| **HTTPS** | HTTP Secure | The encrypted web address; headsets only allow VR on HTTPS pages. |
| **LAN** | Local area network | The home/office network; dtlite runs on it. |
| **API** | Application programming interface | A service programs talk to, e.g. the Overpass API that delivers OSM data. |
| **UTC** | Coordinated Universal Time | Time zone of the build and data timestamps. |
| **JPEG, PDF, CSV** | — | Image, document and table file formats. |
