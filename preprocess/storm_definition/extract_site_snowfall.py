"""Hourly ERA5 snowfall at the example sites, Sep 1990 - Apr 2021, for the storm-definition sensitivity test.

Reads the SNAP ERA5 holdings in place (60-90N slab per month, then picks the site cells) and writes
<OUT_ROOT>/storm_definition/sf_sites.nc (variables = sites, m w.e. per hour). I/O-bound: ~15 min with 16 workers.

Usage (from preprocess/storm_definition/): sbatch extract_site_snowfall.slurm
"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import netCDF4
import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import out_path  # noqa: E402
from step10_reduce_snowfall import SF_DIR  # noqa: E402

SITES = {"fairbanks": (64.84, -147.72), "utqiagvik": (71.29, -156.79), "yellowknife": (62.45, -114.37),
         "eureka": (79.99, -85.93), "pituffik": (76.53, -68.70), "tromso": (69.65, 18.96), "norilsk": (69.35, 88.20),
         "oymyakon": (63.46, 142.79), "valdez": (61.13, -146.35)}
IDX = {k: (int(round((90 - la) / 0.25)), int(round((lo % 360) / 0.25))) for k, (la, lo) in SITES.items()}
MONTHS = [(y, m) for y in range(1990, 2022) for m in (1, 2, 3, 4, 9, 10, 11, 12) if (1990, 9) <= (y, m) <= (2021, 4)]


def one(ym):
    y, m = ym
    with netCDF4.Dataset(f"{SF_DIR}/reanalysis-era5-single-levels_sf_{y}_{m:02d}.nc") as nc:
        a = np.asarray(nc["sf"][:, 0:121, :], dtype=np.float32)
        t = netCDF4.num2date(nc["time"][:], nc["time"].units, only_use_python_datetimes=True,
                             only_use_cftime_datetimes=False)
    return np.array(t, dtype="datetime64[ns]"), {k: a[:, i, j] for k, (i, j) in IDX.items()}


if __name__ == "__main__":
    t0 = time.time()
    with Pool(16) as p:
        res = p.map(one, MONTHS)
    t = np.concatenate([r[0] for r in res])
    ds = xr.Dataset({k: ("time", np.concatenate([r[1][k] for r in res])) for k in SITES}, coords={"time": t},
                    attrs={"source": SF_DIR, "units": "m of water equivalent per hour"})
    dest = out_path("storm_definition", "sf_sites.nc")
    ds.to_netcdf(dest)
    print("wrote", dest, f"{time.time() - t0:.0f}s", dict(ds.sizes))
