"""Step 9: exact frostbite danger classes from hourly air temperature and wind speed (TR-26-5 Eq. 5, Tables 4-5).

One task per calendar day (Feb 29 excluded). For each of the 720 hours (30 years x 24 h) it reads the raw 2T and
WS10 files (the same readers as step 6), computes the time to frostbite of exposed, dry cheek skin with TR-26-5
Eq. 5 (Nelson et al. 2002), exactly as published:

    FT [min] = (-24.5 * (0.667 * WSPD[mph] * 8/5 + 4.8) + 2111) * (-4.8 - (2T[degF] - 32) * 5/9) ** -1.668

and writes intermediate/frostbite/{mon}_{DD}.nc with, per cell:
    counts(bin, lat, lon)   hours per frostbite-time bin: bin u holds hours with previous edge < FT <= u minutes
                            (edges FT_EDGES; the first bin starts at 0), plus two open classes:
                            u = 9999 "longer than 120 min" and u = 99999 "no frostbite" (air at or above -4.8 degC
                            = 23.36 degF, where Eq. 5 is undefined)
    ft_min                  shortest frostbite time in the 720 hours (minutes; NaN if never defined)
Danger classes (TR-26-5 Table 4 labels, Table 5 shows 5 min as red):
    red FT <= 5, amber 5 < FT <= 45, green 45 < FT <= 120, none otherwise.
Above ~76 mph the wind term of Eq. 5 turns negative; such hours are set to FT = 0 (red) and counted in
n_hours_wind_over_eq5_range.

Usage: python step9_reduce_frostbite.py [--days jan_15 ...] [--workers N]
"""
import argparse
import os
import time
from multiprocessing import Pool

import numpy as np
import xarray as xr

from config import DAYS, HOURS, LAT, LON, YEARS, out_path
from step6_reduce_extra import files_for, read

KN_TO_MPH = 1852.0 / 1609.344
FT_EDGES = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30, 35, 40, 45, 60, 75, 90, 105, 120],
                    np.float64)
OVER_120, UNDEFINED = 9999.0, 99999.0
BIN_EDGES = np.concatenate([FT_EDGES, [OVER_120, UNDEFINED]])
CLASSES = {"red": (0.0, 5.0), "amber": (5.0, 45.0), "green": (45.0, 120.0)}  # (lower, upper]


def frostbite_minutes(t2_f, wspd_mph):
    """TR-26-5 Eq. 5. Returns FT in minutes; +inf where undefined (air temperature >= -4.8 degC)."""
    x = -4.8 - (t2_f - 32.0) * 5.0 / 9.0
    wind = -24.5 * (0.667 * wspd_mph * 8.0 / 5.0 + 4.8) + 2111.0
    with np.errstate(divide="ignore", invalid="ignore"):
        ft = np.where(x > 0, np.maximum(wind, 0.0) * np.power(np.where(x > 0, x, 1.0), -1.668), np.inf)
    return ft, (x > 0) & (wind <= 0)


def bin_index(ft):
    """Index into BIN_EDGES: searchsorted on the finite edges; >120 -> OVER_120; inf -> UNDEFINED."""
    idx = np.searchsorted(FT_EDGES, ft, side="left")  # first edge >= ft, so bin u holds prev < ft <= u
    idx[np.isinf(ft)] = len(FT_EDGES) + 1
    return idx  # finite ft > 120 lands at len(FT_EDGES), the OVER_120 bin


def day_task(md):
    m, d = md
    dest = out_path("intermediate", "frostbite", f"{m}_{d:02d}.nc")
    if dest.exists():
        return f"{m}_{d:02d} exists, skipped"
    t0 = time.time()
    tf, wf = files_for("t2", m, d), files_for("wspd", m, d)
    shape = (len(LAT), len(LON))
    ncell, nb = shape[0] * shape[1], len(BIN_EDGES)
    counts = np.zeros((nb, ncell), np.int32)
    ft_min = np.full(ncell, np.inf)
    cells = np.arange(ncell)
    n_wind = 0
    for y in YEARS:
        for h in HOURS:
            t2 = read("t2", tf[(y, h)]).ravel()
            mph = read("wspd", wf[(y, h)]).ravel() * KN_TO_MPH
            ft, over = frostbite_minutes(t2, mph)
            n_wind += int(over.sum())
            counts[bin_index(ft), cells] += 1  # one index per cell, so no duplicates
            np.fmin(ft_min, ft, out=ft_min)
    ft_min[np.isinf(ft_min)] = np.nan
    ds = xr.Dataset(
        {"counts": (("bin", "lat", "lon"), counts.reshape(nb, *shape).astype(np.int16)),
         "ft_min": (("lat", "lon"), ft_min.reshape(shape).astype(np.float32))},
        coords={"bin": BIN_EDGES.astype(np.float32), "lat": LAT, "lon": LON},
        attrs={"calendar_day": f"{m}_{d:02d}", "n_hours": len(YEARS) * len(HOURS),
               "n_hours_wind_over_eq5_range": n_wind,
               "comment": "bin u holds hours with previous edge < FT <= u (min); 9999 = FT > 120; 99999 = undefined"})
    tmp = dest.with_suffix(".tmp")
    ds.to_netcdf(tmp, encoding={"counts": {"zlib": True, "complevel": 2}, "ft_min": {"zlib": True, "complevel": 2}})
    os.replace(tmp, dest)
    return f"{m}_{d:02d} done in {time.time() - t0:.0f}s (wind beyond Eq. 5 range: {n_wind} cell-hours)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", nargs="+", help="e.g. jan_15 (default: all 182)")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", 4)))
    args = ap.parse_args()
    days = [(m, d) for m, d in DAYS if not args.days or f"{m}_{d:02d}" in args.days]
    t0 = time.time()
    with Pool(min(args.workers, len(days))) as pool:
        for msg in pool.imap_unordered(day_task, days):
            print(msg, flush=True)
    print(f"step9 finished {len(days)} days in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
