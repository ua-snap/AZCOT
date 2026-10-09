"""Step 10: 24-hour and storm-total snowfall loads from ERA5 hourly snowfall (SNAP holdings, read in place).

TR-26-5 (snow-load design criteria): tentage must withstand 24-hour snowfalls up to 10 lb/ft2; rigid shelters and
portable hangars must withstand snowfalls from storms lasting longer than one day up to 20 lb/ft2, being "cleared of
snow between storms". Neither is the snow on the ground (that is snow load, SL, from SWE in steps 1-5); both need the
snowfall itself, which AZCOT does not have. SWE differencing does not work (ERA5 analysis increments, see README).

Source: /import/AKCASC/data/cds/reanalysis-era5-single-levels/sf (ERA5 'sf', m of water equivalent accumulated over
the hour ending at the time stamp; global 0.25 degree, monthly files, int16-packed with per-file scale/offset).
Never written to. Load = water equivalent x 204.724 lb/ft2 per m (TR-26-5 eq. 4, the same factor as SL).

One task per winter (Oct Y - Mar Y+1, Y = 1990 ... 2020), read as one continuous hourly series from Sep 1 to Apr 30 so
that 24-hour windows and storms that cross month, year or season edges are complete. Only AZCOT months are kept
(Jan-Mar 1991-2020 and Oct-Dec 1991-2020), so every calendar day pools 30 years like the other coverages. Feb 29 hours
are part of the series (snow that falls on Feb 29 is real) but no Feb 29 calendar day is written.

Per winter: intermediate/snowfall/winter_{Y}.nc with, for each kept calendar day and cell,
    sf24_daymax   largest trailing 24-hour snowfall load among the 24 windows ending in that day's hours (lb/ft2)
    storm_max     largest storm-total load among storms ENDING that day (lb/ft2; 0 if none ended). A storm that is
                  still going at the end of Mar 31 is credited to Mar 31 with its full total.
    storm_hours   duration (h) of that storm
    sf72_daymax   largest trailing 72-hour snowfall load ending in that day (a storm measure that needs no storm
                  definition; used to cross-check storm_max)
Storm: a run of wet hours (snowfall >= WET_MM_H mm w.e.) in which dry gaps are at most GAP_H hours; its total is all
snowfall from its first to its last wet hour. GAP_H = 12: a half-day lull is taken as the chance to clear a shelter
("cleared of snow between storms"). Tested at 9 sites (wet 0.05/0.1/0.2 mm/h x gap 6/12/24 h): away from maritime
climates nothing changes; at Tromso and Valdez a 24-h gap chains storms for 30-40 days (seasonal accumulation, not a
storm), while 12 h gives multi-day storms of up to ~2 weeks and 6 h splits obvious multi-day events.
The definition is ours (TR-26-5 gives none): rationale, sensitivity results and how to change it are in
storm_definition/README.md.

Usage: python step10_reduce_snowfall.py [--winters 1995 ...] [--workers N]
"""
import argparse
import datetime as dt
import os
import time
from multiprocessing import Pool

import netCDF4
import numpy as np
import xarray as xr

from config import LAT, LON, SWE_M_TO_SL, YEARS, out_path

SF_DIR = "/import/AKCASC/data/cds/reanalysis-era5-single-levels/sf"
WET_MM_H = 0.1   # mm water equivalent per hour (= 0.02 lb/ft2/h); lighter hours count as dry
GAP_H = 12       # longest dry gap (hours) inside one storm
BANDS = 16       # latitude bands processed separately to bound memory (~6 GB per worker)
AZCOT_MONTHS = {10, 11, 12, 1, 2, 3}


def read_month(y, m):
    """(times, int16 counts, scale, offset) for 60-90N, lon reordered to -180 ... 179.75, lat ascending."""
    with netCDF4.Dataset(f"{SF_DIR}/reanalysis-era5-single-levels_sf_{y}_{m:02d}.nc") as nc:
        lat = nc["latitude"][0:121]
        lon = nc["longitude"][:]
        if not (abs(lat[0] - 90) < 1e-4 and abs(lat[-1] - 60) < 1e-4 and abs(lon[0]) < 1e-4 and len(lon) == 1440):
            raise ValueError(f"unexpected grid in sf {y}-{m:02d}")
        v = nc["sf"]
        v.set_auto_maskandscale(False)
        raw = np.asarray(v[:, 0:121, :])
        scale, offset = float(v.scale_factor), float(v.add_offset)
        fill = int(v._FillValue)
        t = netCDF4.num2date(nc["time"][:], nc["time"].units, only_use_python_datetimes=True,
                             only_use_cftime_datetimes=False)
    if (raw == fill).any():
        raise ValueError(f"fill values in sf {y}-{m:02d}")
    raw = np.roll(raw[:, ::-1, :], 720, axis=2)  # lat 60 -> 90; lon 0..359.75 -> -180..179.75
    return np.array(t, dtype="datetime64[h]"), raw, scale, offset


def run_lengths(wet):
    """Storm membership along axis 0: wet hours plus dry gaps of at most GAP_H between wet hours."""
    T = wet.shape[0]
    idx = np.arange(T)[:, None]
    last = np.where(wet, idx, -10**9)
    np.maximum.accumulate(last, axis=0, out=last)
    nxt = np.where(wet, idx, 10**9)
    nxt = np.minimum.accumulate(nxt[::-1], axis=0)[::-1]
    return wet | ((nxt - last - 1) <= GAP_H)


def loads(sf, h_last):
    """Hourly (T, cells) snowfall in m w.e. -> trailing 24-h sums, storm totals and durations at storm-end hours.

    A storm still running at hour h_last is credited to h_last with its full total (to its true end later).
    """
    T = sf.shape[0]
    wet_thr = WET_MM_H / 1000.0  # m w.e.
    csum = np.cumsum(sf, axis=0, dtype=np.float64)  # m w.e.
    # Trailing 24- and 72-hour sums ending at each hour (the first hours of Sep are incomplete; never kept).
    s24 = csum.copy()
    s24[24:] -= csum[:-24]
    s72 = csum.copy()
    s72[72:] -= csum[:-72]
    # Storms
    inst = run_lengths(sf >= wet_thr)
    prev = np.vstack([np.zeros((1, inst.shape[1]), bool), inst[:-1]])
    nxt = np.vstack([inst[1:], np.zeros((1, inst.shape[1]), bool)])
    start = inst & ~prev
    end = inst & ~nxt
    # cumulative sum just before each storm start, carried forward through the storm
    base = np.where(start, np.vstack([np.zeros((1, csum.shape[1])), csum[:-1]]), np.nan)
    start_idx = np.where(start, np.arange(T)[:, None], -1)
    np.maximum.accumulate(start_idx, axis=0, out=start_idx)
    rows = np.clip(start_idx, 0, None)
    base_ff = np.take_along_axis(np.nan_to_num(base, nan=0.0), rows, axis=0)
    total = np.where(end, csum - base_ff, 0.0)
    dur = np.where(end, np.arange(T)[:, None] - rows + 1, 0)
    # A storm still running at the last kept hour (end of Mar 31 or Dec 31 2020) is credited to that hour.
    running = inst[h_last] & ~end[h_last]
    if running.any():
        # its full total: from its start to its true end later in the series
        later_end = end[h_last + 1:]
        first_end = np.argmax(later_end, axis=0) + h_last + 1
        has_end = later_end.any(axis=0)
        fe = np.where(has_end, first_end, T - 1)
        cells = np.flatnonzero(running)
        total[h_last, cells] = csum[fe[cells], cells] - base_ff[h_last, cells]
        dur[h_last, cells] = fe[cells] - rows[h_last, cells] + 1
    return s24, s72, total, dur


def winter_task(Y):
    dest = out_path("intermediate", "snowfall", f"winter_{Y}.nc")
    if dest.exists():
        return f"winter {Y} exists, skipped"
    t0 = time.time()
    months = [(Y, m) for m in (9, 10, 11, 12)] + [(Y + 1, m) for m in (1, 2, 3, 4)]
    parts = [read_month(y, m) for y, m in months]
    times = np.concatenate([p[0] for p in parts])
    if not (np.diff(times) == np.timedelta64(1, "h")).all():
        raise ValueError(f"winter {Y}: hourly series has gaps")
    # Calendar days kept: AZCOT months of AZCOT years, Feb 29 excluded.
    day_of = times.astype("datetime64[D]")
    keep_days = []
    for d in np.unique(day_of):
        pd_ = d.astype(dt.date)
        if pd_.month in AZCOT_MONTHS and pd_.year in YEARS and not (pd_.month == 2 and pd_.day == 29):
            keep_days.append(d)
    keep_days = np.array(keep_days)
    last_kept_hour = (keep_days[-1] + np.timedelta64(1, "D")).astype("datetime64[h]") - np.timedelta64(1, "h")
    nd, ny, nx = len(keep_days), len(LAT), len(LON)
    sf24 = np.zeros((nd, ny, nx), np.float32)
    smax = np.zeros((nd, ny, nx), np.float32)
    shours = np.zeros((nd, ny, nx), np.int16)
    sf72 = np.zeros((nd, ny, nx), np.float32)
    day_index = {d: i for i, d in enumerate(keep_days)}
    hour_day = np.array([day_index.get(d, -1) for d in day_of])
    for band in np.array_split(np.arange(ny), BANDS):
        sf = np.concatenate([(p[1][:, band, :].astype(np.float32) * np.float32(p[2]) + np.float32(p[3]))
                             for p in parts]).reshape(len(times), -1)
        np.maximum(sf, 0.0, out=sf)  # packing noise
        h_last = int(np.flatnonzero(times == last_kept_hour)[0])
        s24, s72, total, dur = loads(sf, h_last)
        # Reduce hours -> kept calendar days
        bsl = slice(band[0], band[-1] + 1)
        for i in range(nd):
            hrs = np.flatnonzero(hour_day == i)
            sf24[i, bsl] = (s24[hrs].max(axis=0) * SWE_M_TO_SL).reshape(len(band), nx)
            sf72[i, bsl] = (s72[hrs].max(axis=0) * SWE_M_TO_SL).reshape(len(band), nx)
            t = total[hrs]
            k = t.argmax(axis=0)
            smax[i, bsl] = (t.max(axis=0) * SWE_M_TO_SL).reshape(len(band), nx)
            shours[i, bsl] = np.take_along_axis(dur[hrs], k[None], axis=0)[0].reshape(len(band), nx)
        del sf, s24, s72, total, dur
    dates = keep_days.astype("datetime64[ns]")
    ds = xr.Dataset({"sf24_daymax": (("date", "lat", "lon"), sf24),
                     "storm_max": (("date", "lat", "lon"), smax),
                     "storm_hours": (("date", "lat", "lon"), shours),
                     "sf72_daymax": (("date", "lat", "lon"), sf72)},
                    coords={"date": dates, "lat": LAT, "lon": LON},
                    attrs={"winter": Y, "wet_mm_per_hour": WET_MM_H, "gap_hours": GAP_H,
                           "source": SF_DIR, "units": "lbf ft-2 (storm_hours: h)"})
    tmp = dest.with_suffix(".tmp")
    ds.to_netcdf(tmp, encoding={v: {"zlib": True, "complevel": 2} for v in ds.data_vars})
    os.replace(tmp, dest)
    return f"winter {Y}: {nd} days in {time.time() - t0:.0f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--winters", nargs="+", type=int, default=list(range(1990, 2021)))
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", 4)))
    args = ap.parse_args()
    t0 = time.time()
    with Pool(min(args.workers, len(args.winters))) as pool:
        for msg in pool.imap_unordered(winter_task, args.winters):
            print(msg, flush=True)
    print(f"step10 finished {len(args.winters)} winters in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
