"""Generate a synthetic DEM + ortho and run build_usd, to verify the pipeline
without needing the real Hessen download. Drops outputs into data/prep_demo/
and out/demo/."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_origin


def main() -> None:
    prep = Path("data/prep_demo")
    out = Path("out/demo")
    prep.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    # 300x300 m synthetic DEM with a depression in the middle (faux pit).
    N = 300
    ys, xs = np.mgrid[0:N, 0:N].astype("float32")
    cx, cy, r = N / 2, N / 2, 60
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    base = 160.0 + 10.0 * np.sin(xs / 30.0) + 10.0 * np.cos(ys / 30.0)
    pit = -40.0 * np.clip(1.0 - d / r, 0.0, 1.0) ** 2
    dem = (base + pit).astype("float32")

    transform = from_origin(0.0, N, 1.0, 1.0)
    dem_path = prep / "dem.tif"
    with rasterio.open(
        dem_path, "w", driver="GTiff", height=N, width=N, count=1,
        dtype="float32", transform=transform, compress="lzw", tiled=True,
    ) as dst:
        dst.write(dem, 1)

    # Synthetic "ortho": gradient + a darker disc where the pit is.
    rgb = np.zeros((N, N, 3), dtype="uint8")
    rgb[..., 0] = (60 + xs * 0.4).clip(0, 255).astype("uint8")
    rgb[..., 1] = (90 + ys * 0.3).clip(0, 255).astype("uint8")
    rgb[..., 2] = 40
    mask = d < r
    rgb[mask] = (rgb[mask] * 0.4).astype("uint8")
    Image.fromarray(rgb, mode="RGB").save(prep / "ortho.png")

    (prep / "origin.json").write_text(json.dumps({
        "utm_zone": "32N", "epsg": 25832,
        "utm_sw_easting": 0, "utm_sw_northing": 0,
        "width_m": N, "height_m": N,
        "dem_resolution_m": 1.0, "ortho_resolution_m": 1.0,
        "dem_stats": {
            "min": float(dem.min()), "max": float(dem.max()),
            "mean": float(dem.mean()), "shape": [N, N],
        },
    }, indent=2))

    print(f"Synthetic DEM range: {dem.min():.1f}..{dem.max():.1f} m")
    cmd = [
        sys.executable, "-m", "messelpit.build_usd",
        "-i", str(prep), "-o", str(out / "demo.usd"), "-z",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
