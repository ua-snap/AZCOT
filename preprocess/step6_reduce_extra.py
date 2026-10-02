"""Step 6: air temperature (2T), 10 m wind speed (WSPD) and snow depth (SD) from the raw hourly files.

One task per (variable, month). For every day in the month (Feb 29 excluded) it reads the 720 hourly fields
(30 years x 24 h) and writes, like step 1:
    intermediate/hourly_reduce/{t2,wspd,sd}/{mon}_{DD}.nc    min / mean / max / mean_annual_min / mean_annual_max
and, for the whole month:
    intermediate/histograms/{var}_{mon}.nc                   counts of hourly values in unit bins
    intermediate/freeze_thaw/t2_{mon}.nc                     (t2 only) freeze-thaw days per year
Units are converted at the source: 2T K -> degF; WS10 m/s -> knots (the raw "*_knots.nc" files are really m/s);
SD m -> inches. SD stays on its native ERA5-Land 0.1-degree grid (NaN over water).

Histogram bins are labelled by their upper edge u and hold hours with u-1 < x <= u, so for an integer threshold T
the count of hours with x <= T is the sum of bins u <= T. The lowest and highest bins collect everything beyond.
Hours whose field is entirely NaN (missing in the source; e.g. SD 2008-12-01 00 UTC) are skipped and listed in the
day's n_missing_hours and the histogram's missing_hours attribute; any partial change of the data mask is an error.
A month is atomic: if its histogram exists it is skipped; otherwise the whole month is recomputed.

Usage: python step6_reduce_extra.py [--vars t2 wspd sd] [--months jan ...] [--workers N]
"""
import argparse
import os
import time
from multiprocessing import Pool

import numpy as np
import xarray as xr

from config import (DAYS, HOURS, LAT, LON, MONTH_NUM, MONTHS, RAW, SD_LAT, SD_LON, YEARS, out_path)

SPEC = {
    "t2": {"raw": "2T", "var": "2T_GDS0_SFC", "units": "degF", "bins": (-120, 80),
           "convert": lambda k: (k - 273.15) * 9.0 / 5.0 + 32.0, "grid": "era5"},
    "wspd": {"raw": "WS10_knots", "var": "WS10", "units": "knots", "bins": (0, 120),
             "convert": lambda ms: ms * 1.943844, "grid": "era5"},
    "sd": {"raw": "SD", "var": "sde", "units": "inches", "bins": (0, 120),
           "convert": lambda m: np.maximum(m, 0.0) * 39.3701, "grid": "era5land"},
}
FREEZE_F = 32.0


def grid(name):
    return (LAT, LON) if SPEC[name]["grid"] == "era5" else (SD_LAT, SD_LON)


def read(name, path):
    s = SPEC[name]
    with xr.open_dataset(path) as ds:  # read-only
        a = ds[s["var"]].values.astype(np.float64)
        lat = ds[ds[s["var"]].dims[0]].values
    lat_out, lon_out = grid(name)
    if a.shape != (len(lat_out), len(lon_out)) or not lat[0] > lat[-1]:
        raise ValueError(f"unexpected grid in {path}: {a.shape}, lat {lat[0]}..{lat[-1]}")
    return s["convert"](a[::-1])  # -> lat ascending


def files_for(name, m, d):
    folder = RAW / m / f"{d:02d}"
    out = {}
    for f in folder.glob(f"??{MONTH_NUM[m]:02d}{d:02d}??.{SPEC[name]['raw']}.nc"):
        yy, hh = int(f.name[0:2]), int(f.name[6:8])
        out[(1900 + yy if yy >= 50 else 2000 + yy, hh)] = f
    expected = {(y, h) for y in YEARS for h in HOURS}
    if set(out) != expected:
        raise ValueError(f"{name} {m}_{d:02d}: {len(out)} files, expected 720")
    return out


def month_task(task):
    name, month = task
    hist_dest = out_path("intermediate", "histograms", f"{name}_{month}.nc")
    if hist_dest.exists():
        return f"{name} {month} exists, skipped"
    t0 = time.time()
    lat, lon = grid(name)
    shape = (len(lat), len(lon))
    lo, hi = SPEC[name]["bins"]
    edges = np.arange(lo, hi + 1)  # bin upper edges
    nb = len(edges)
    valid = None  # cells with data (SD: land only)
    counts = None
    ft_days = np.zeros(shape)
    days = [(m, d) for m, d in DAYS if m == month]
    missing = []  # (year, month, day, hour) of hours whose field is entirely NaN (missing in the source)
    for m, d in days:
        files = files_for(name, m, d)
        total = np.zeros(shape)
        gmin, gmax = np.full(shape, np.inf), np.full(shape, -np.inf)
        sum_ymin, sum_ymax = np.zeros(shape), np.zeros(shape)
        n_day = 0
        for y in YEARS:
            ymin, ymax = np.full(shape, np.inf), np.full(shape, -np.inf)
            for h in HOURS:
                a = read(name, files[(y, h)])
                if not np.isfinite(a).any():
                    missing.append(f"{y}-{MONTH_NUM[m]:02d}-{d:02d}T{h:02d}")
                    continue
                n_day += 1
                if valid is None:
                    valid = np.isfinite(a)
                    cells = np.flatnonzero(valid)
                    counts = np.zeros(nb * cells.size, np.int32)
                elif not np.array_equal(np.isfinite(a), valid):
                    raise ValueError(f"data mask changed in {files[(y, h)]}")
                total += np.where(valid, a, 0.0)
                np.fmin(ymin, a, out=ymin)
                np.fmax(ymax, a, out=ymax)
                idx = np.clip(np.ceil(a.ravel()[cells]) - lo, 0, nb - 1).astype(np.int64)
                np.add.at(counts, idx * cells.size + np.arange(cells.size), 1)
            np.fmin(gmin, ymin, out=gmin)
            np.fmax(gmax, ymax, out=gmax)
            sum_ymin += ymin
            sum_ymax += ymax
            if name == "t2":
                ft_days += (ymin < FREEZE_F) & (ymax > FREEZE_F)
        n = n_day
        dims = ("lat", "lon")
        mask = lambda x: np.where(valid, x, np.nan).astype(np.float32)
        ds = xr.Dataset({"min": (dims, mask(gmin)), "mean": (dims, mask(total / n)), "max": (dims, mask(gmax)),
                         "mean_annual_min": (dims, mask(sum_ymin / len(YEARS))),
                         "mean_annual_max": (dims, mask(sum_ymax / len(YEARS)))},
                        coords={"lat": lat, "lon": lon},
                        attrs={"variable": name, "calendar_day": f"{m}_{d:02d}", "n_hours": n,
                               "n_missing_hours": len(files) - n, "units": SPEC[name]["units"]})
        dest = out_path("intermediate", "hourly_reduce", name, f"{m}_{d:02d}.nc")
        tmp = dest.with_suffix(".tmp")
        ds.to_netcdf(tmp, encoding={v: {"zlib": True, "complevel": 1} for v in ds.data_vars})
        os.replace(tmp, dest)

    full = np.zeros((nb, shape[0] * shape[1]), np.int32)
    full[:, cells] = counts.reshape(nb, cells.size)
    h = xr.Dataset({"counts": (("bin", "lat", "lon"), full.reshape(nb, *shape))},
                   coords={"bin": ("bin", edges.astype(np.float32),
                                   {"long_name": f"bin upper edge; bin holds hours with edge-1 < x <= edge "
                                                 f"(first/last bins open-ended)", "units": SPEC[name]["units"]}),
                           "lat": lat, "lon": lon},
                   attrs={"variable": name, "month": month, "n_days": len(days),
                          "n_hours": 720 * len(days) - len(missing), "missing_hours": ", ".join(missing) or "none"})
    tmp = hist_dest.with_suffix(".tmp")
    h.to_netcdf(tmp, encoding={"counts": {"zlib": True, "complevel": 2, "dtype": "int16",
                                          "chunksizes": (1, shape[0], shape[1])}})
    if name == "t2":
        ftd = xr.Dataset({"freeze_thaw_days": (("lat", "lon"), (ft_days / len(YEARS)).astype(np.float32),
                                               {"long_name": "days per year with hourly 2T both below and above 32F",
                                                "units": "days"})},
                         coords={"lat": lat, "lon": lon}, attrs={"month": month, "n_days": len(days)})
        ftd.to_netcdf(out_path("intermediate", "freeze_thaw", f"t2_{month}.nc"))
    os.replace(tmp, hist_dest)  # histogram last: its presence marks the month complete
    return f"{name} {month} done in {time.time() - t0:.0f}s; missing (all-NaN) hours: {missing or 'none'}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vars", nargs="+", default=list(SPEC), choices=list(SPEC))
    ap.add_argument("--months", nargs="+", default=MONTHS, choices=MONTHS)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", 4)))
    args = ap.parse_args()
    tasks = [(v, m) for v in args.vars for m in args.months]
    t0 = time.time()
    with Pool(min(args.workers, len(tasks))) as pool:
        for msg in pool.imap_unordered(month_task, tasks):
            print(msg, flush=True)
    print(f"step6 finished {len(tasks)} tasks in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
