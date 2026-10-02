"""Step 1: reduce the 720 raw hourly fields per calendar day to per-cell min / mean / max.

For each variable (WCT from hourly .nc, SL from hourly SWE .grib) and each of the 182 cold-season
days (Feb 29 excluded), read all 30 years x 24 hours and write
    intermediate/hourly_reduce/{wct,sl}/{mon}_{DD}.nc
with float32 fields on the output grid (lat ascending):
    min, mean, max                       - true statistics of the 720 hourly values
    mean_annual_min, mean_annual_max     - mean over years of each year's daily extreme (validation only;
                                           reproduces Metrics min_WCT)
Sources are opened read-only. Finished days are skipped, so the step can be re-run after an interruption.

Usage: python step1_reduce_hourly.py [--vars WCT SL] [--workers N] [--days jan_15 ...]
"""
import argparse
import os
import time
from multiprocessing import Pool

import eccodes
import numpy as np
import xarray as xr

from config import DAYS, HOURS, LAT, LON, SWE_M_TO_SL, YEARS, out_path, raw_files

NLAT, NLON = len(LAT), len(LON)


def read_wct(path):
    with xr.open_dataset(path) as ds:  # read-only
        lat = ds["g0_lat_0"].values
        a = ds["WCT"].values.astype(np.float64)
    if not (a.shape == (NLAT, NLON) and lat[0] > lat[-1]):
        raise ValueError(f"unexpected grid in {path}: shape {a.shape}, lat {lat[0]}..{lat[-1]}")
    return a[::-1]  # -> lat ascending


def read_swe(path, year, hour):
    with open(path, "rb") as fh:  # read-only
        g = eccodes.codes_grib_new_from_file(fh)
        try:
            ni, nj = eccodes.codes_get(g, "Ni"), eccodes.codes_get(g, "Nj")
            jpos = eccodes.codes_get(g, "jScansPositively")
            date, tod = eccodes.codes_get(g, "dataDate"), eccodes.codes_get(g, "dataTime")
            name = eccodes.codes_get(g, "shortName")
            vals = eccodes.codes_get_values(g)
        finally:
            eccodes.codes_release(g)
        if eccodes.codes_grib_new_from_file(fh) is not None:
            raise ValueError(f"more than one GRIB message in {path}")
    if (ni, nj, jpos, name) != (NLON, NLAT, 0, "sd"):
        raise ValueError(f"unexpected GRIB layout in {path}: {ni}x{nj} jScansPositively={jpos} {name}")
    if date // 10000 != year or tod != hour * 100:
        raise ValueError(f"GRIB date {date} {tod} does not match filename {path.name}")
    return vals.reshape(NLAT, NLON)[::-1].astype(np.float64) * SWE_M_TO_SL  # -> lat ascending, lb/ft2


def reduce_day(task):
    var, month, day = task
    dest = out_path("intermediate", "hourly_reduce", var.lower(), f"{month}_{day:02d}.nc")
    if dest.exists():
        return f"{var} {month}_{day:02d} exists, skipped"
    t0 = time.time()
    files = raw_files("WCT" if var == "WCT" else "SWE", month, day)
    expected = {(y, h) for y in YEARS for h in HOURS}
    if set(files) != expected:
        missing = sorted(expected - set(files))[:5]
        extra = sorted(set(files) - expected)[:5]
        raise ValueError(f"{var} {month}_{day:02d}: {len(files)} files; missing {missing} extra {extra}")

    total = np.zeros((NLAT, NLON))
    gmin = np.full((NLAT, NLON), np.inf)
    gmax = np.full((NLAT, NLON), -np.inf)
    sum_ymin = np.zeros((NLAT, NLON))
    sum_ymax = np.zeros((NLAT, NLON))
    for y in YEARS:
        ymin = np.full((NLAT, NLON), np.inf)
        ymax = np.full((NLAT, NLON), -np.inf)
        for h in HOURS:
            a = read_wct(files[(y, h)]) if var == "WCT" else read_swe(files[(y, h)], y, h)
            if not np.isfinite(a).all():
                raise ValueError(f"non-finite values in {files[(y, h)]}")
            total += a
            np.minimum(ymin, a, out=ymin)
            np.maximum(ymax, a, out=ymax)
        np.minimum(gmin, ymin, out=gmin)
        np.maximum(gmax, ymax, out=gmax)
        sum_ymin += ymin
        sum_ymax += ymax
    n = len(expected)

    dims = ("lat", "lon")
    ds = xr.Dataset(
        {
            "min": (dims, gmin.astype(np.float32)),
            "mean": (dims, (total / n).astype(np.float32)),
            "max": (dims, gmax.astype(np.float32)),
            "mean_annual_min": (dims, (sum_ymin / len(YEARS)).astype(np.float32)),
            "mean_annual_max": (dims, (sum_ymax / len(YEARS)).astype(np.float32)),
        },
        coords={"lat": LAT, "lon": LON},
        attrs={"variable": var, "calendar_day": f"{month}_{day:02d}", "n_hours": n,
               "units": "degF" if var == "WCT" else "lbf ft-2"},
    )
    tmp = dest.with_suffix(".tmp")
    ds.to_netcdf(tmp, encoding={v: {"zlib": True, "complevel": 1} for v in ds.data_vars})
    os.replace(tmp, dest)  # atomic: a crash never leaves a half-written day behind
    return f"{var} {month}_{day:02d} done in {time.time() - t0:.1f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vars", nargs="+", default=["WCT", "SL"], choices=["WCT", "SL"])
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", 4)))
    ap.add_argument("--days", nargs="*", help="subset like jan_15 (default: all 182)")
    args = ap.parse_args()
    days = DAYS if not args.days else [(d.split("_")[0], int(d.split("_")[1])) for d in args.days]
    if any(d == ("feb", 29) for d in days):
        raise SystemExit("Feb 29 is excluded by design")
    tasks = [(v, m, d) for v in args.vars for m, d in days]
    t0 = time.time()
    with Pool(args.workers) as pool:
        for msg in pool.imap_unordered(reduce_day, tasks):
            print(msg, flush=True)
    print(f"step1 finished {len(tasks)} tasks in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
