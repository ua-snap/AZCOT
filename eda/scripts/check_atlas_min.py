"""Compare the Atlas 'Minimum' WCT rasters (disk2) with disk1/Metrics min_WCT and percentile_1.

The Atlas keeps the GeoTIFF each PDF map was rendered from. Result (2026-10-02): the rasters hold the TRUE
30-year hourly minimum, while Metrics min_WCT holds the mean of annual minima.
"""
from pathlib import Path

import numpy as np
from PIL import Image

from azcot import load_cube, load_masks

ATLAS = Path("/import/beegfs/SNAP/rltorgerson/AZCOT/disk2/Atlas")


def read_tif(path):
    """Atlas raster -> (121, 1440) array on the Metrics grid (lat ascending, wrap column dropped)."""
    a = np.array(Image.open(path), dtype=np.float64)
    a[a < -1e30] = np.nan
    return a[::-1, :1440]


def main():
    wct = load_cube("wct")
    print("day     cells  TIF==min_WCT  TIF<=p1  mean(min_WCT-TIF) °F")
    for m, d in [("oct", 15), ("jan", 15), ("feb", 29), ("mar", 1)]:
        t = read_tif(ATLAS / m / "Daily" / f"{d:02d}" / "WCT" / "Extreme" / f"{m}_{d:02d}_WCT_min.tif")
        k = np.isfinite(t)
        day = wct.sel(day=f"{m}_{d:02d}")
        mw, p1 = day.min_WCT.values[k], day.percentile_1.values[k]
        print(f"{m}_{d:02d}  {k.sum():6d}  {100 * np.mean(abs(t[k] - mw) < 0.01):10.2f}%  "
              f"{100 * np.mean(t[k] <= p1 + 1e-3):6.1f}%  {np.mean(mw - t[k]):8.1f}")
    season = read_tif(ATLAS / "Year" / "WCT" / "Extreme" / "year_WCT_min.tif")
    land = load_masks().land.values
    print(f"Season record low, land pixel mean: {np.nanmean(season):.2f} °F (TR-26-5: -86.7); "
          f"area-weighted: {np.nansum(season * np.cos(np.radians(wct.g0_lat_0.values))[:, None]) / np.nansum(np.isfinite(season) * np.cos(np.radians(wct.g0_lat_0.values))[:, None]):.2f}; "
          f"raster cells outside our land mask: {int(np.sum(np.isfinite(season) & ~land))}")


if __name__ == "__main__":
    main()
