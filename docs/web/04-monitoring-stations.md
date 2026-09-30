# Monitoring stations (Nix 2003)

The coloured **pins** are the measuring network set up to watch the pit's slopes, which
have been sliding since the 1930s. The stations are listed, with coordinates, in the
appendix of:

> Nix, T. (2003): Untersuchung der ingenieurgeologischen Verhältnisse der Grube Messel
> (Darmstadt) im Hinblick auf die Langzeitstabilität der Grubenböschungen. —
> Geologische Abhandlungen Hessen 112, 159 pp., HLUG, Wiesbaden.

The PDF is in `dthub/docs/`; notes on the whole monograph are in
`messelpit/docs/messel-nix-2003-notes.md`.

## What the pins are

| Colour | Type | Count | What it measures |
|---|---|---|---|
| dark blue | deep well (GW 1–5) | 5 | groundwater in the crystalline rock, 30–45 m deep |
| light blue | piezometer (KP 101–525) | 100 | shallow groundwater, 3 m |
| red | inclinometer (IN 1–28) | 28 | sideways movement down a 19.5–65 m tube; **"sheared off"** ones were broken by the slides — which itself marks the slip surfaces at 7–49 m depth |
| yellow | fixed geodetic point (F1–F5) | 5 | survey reference points |
| beige | temporary geodetic point (6000–9032) | 33 | GPS survey points |

**Click a pin** to see its name, type, depth, remark, its ground height in the 2001
table and today's ground height at the same spot.

## What the inclinometers measure

An inclinometer shows **how the ground slides sideways, at every depth**.

- A borehole is lined with a tube with four grooves inside. Its foot is anchored in
  stable rock below any moving ground.
- From time to time a probe is run down the grooves and measures the tube's **tilt**
  every half metre or so. Adding the tilts up gives the tube's shape from top to bottom.
- Comparing each survey with the first shows **how far each depth has moved**, and in
  which direction, since the tube was installed.

What the shape tells you:

- A **sharp kink** at one depth is a **slip surface**: the mass above slides as a block
  over the ground below.
- A **gradual bend** is slow creep spread through the soil.
- Repeated surveys give the **speed**: at Messel, millimetres to centimetres a year,
  faster after heavy rain. Nix gives the rain that reactivates the slides as more than
  **105 mm in a month or 35 mm in 72 hours**.

**"Sheared off"** (*abgeschert*, the remark on many inclinometers) means the movement
bent or broke the tube so badly that the probe no longer gets through: that station can
no longer be read. It is still a result, because it pinpoints the slip surface. From
them Nix found slip surfaces at **7–49 m depth**, often at the boundary between the
Lower and Middle Messel Formation. There the beds dip toward the pit centre, and the
upper layers slide on them like a tilted stack of plates.

That is why the network exists: decades after mining ended, the slopes are still
moving. It has been monitored since 1993, and Nix concluded that none of the slopes meet
the German long-term safety factors (DIN 1054).

## How the positions were made

```mermaid
flowchart LR
  P["Nix 2003, appendix 12.1<br/>(scanned table)"] -- "OCR, digits cleaned<br/>by hand" --> C["messel-nix-2003-stations.csv<br/>Gauss–Krüger zone 3"]
  C -- "pyproj EPSG:31467 → 25832<br/>minus scene SW corner" --> G["stations.geojson<br/>scene metres"]
  G --> V["pins on today's terrain"]
```

- The table gives **Gauss–Krüger zone 3** coordinates (DHDN, EPSG:31467), the old German
  system. They are transformed to UTM 32N with a standard datum shift (≈1 m accuracy,
  no grid file) by `messelpit/tools/export_web.py`.
- The table was **scanned text**: the digits were read by OCR and cleaned by hand.

## How good are they?

Checked against today's terrain: the 2001 ground heights of the stations match the DGM1
at a **median of +0.03 m**, and **97 % are within 2 m**. So both the transform and the
transcription hold. Outliers:

- **IN23** is listed at 116.18 m but the ground there is ~160 m (+43.9 m). The scan
  confirms the book really prints 116,18, so this is a **misprint in Nix**, not a
  transcription error. The height is the likely mistake (probably 160,18): the ground at
  the printed position is 160.03 m, and no one-digit slip in the coordinates reaches
  ground at ~116 m. The viewer keeps the printed value and flags it.
- Points 9002 / 9003 (−6 m) lie outside the pit; 9032 (+3.6 m).

The pins stand on **today's** ground, not the 2001 height, so they never float or sink
where the slopes have moved.
