"""Step 11: Level 2 coverages from the step-9 (frostbite) and step-10 (snowfall) intermediates.

Frostbite (TR-26-5 Eq. 5 and Tables 4-5, from hourly 2T and 10 m wind jointly; replaces the wind-chill approximation):
    azcot_frostbite_{daily,monthly,seasonal}.nc
        frostbite_{red,amber,green}_share   % of hours in each danger level:
                                            red FT <= 5 min, amber 5 < FT <= 45, green 45 < FT <= 120
        frostbite_none_share                % of hours with FT > 120 min or no frostbite (air >= 23.36 degF)
        frostbite_time_min                  shortest time to frostbite in any hour (minutes, true minimum)
    azcot_frostbite_histogram_monthly.nc    frostbite_hour_counts(time, bin, lat, lon): hours per frostbite-time bin
Snowfall loads (TR-26-5 design criteria: tentage 10 lb/ft2 from one 24-hour snowfall; rigid shelters 20 lb/ft2 from
one storm lasting longer than a day), from the step-10 per-winter intermediates:
    azcot_snowfall_{daily,monthly,seasonal}.nc
        sf24_max                record 24-hour snowfall load (largest trailing 24-h sum in 30 years), lb/ft2
        sf24_mean_annual_max    mean over the 30 years of each year's largest 24-hour load in the period
        sf24_ge10_years         % of years with at least one 24-hour load >= 10 lb/ft2 in the period (tentage)
        storm_max               record storm-total snowfall load, lb/ft2 (storm credited to the day it ends)
        storm_mean_annual_max   mean over the 30 years of each year's largest storm total in the period
        storm_ge20_years        % of years with at least one storm total >= 20 lb/ft2 in the period (rigid shelters)
        sf72_max, sf72_mean_annual_max   the same for the largest trailing 72-hour load (storm cross-check that needs no
                                storm definition)
      monthly and seasonal also:
        sf24_ge10_days          mean days per year whose largest 24-hour load is >= 10 lb/ft2
        storm_ge20_per_year     mean storms per year with a total >= 20 lb/ft2
    azcot_snowfall_histogram_monthly.nc
        sf24_day_counts(time, sf24_bin, lat, lon)    days per bin of the day's largest 24-hour load (0.5 lb/ft2 bins)
        storm_counts(time, storm_bin, lat, lon)      storms per bin of storm total (1 lb/ft2 bins), by month of end
A "year" is a calendar year's Jan-Mar plus Oct-Dec, the pooling every AZCOT coverage uses (1991-2020).
Every file carries surface_type; nothing is masked (frostbite and snowfall are meaningful over ice and sea ice).
"""
import warnings

import numpy as np
import xarray as xr

from cf import add_time, base_dataset, encoding, finalize, surface_type_attrs
from config import DAYS, INTERMEDIATE, LAT, LON, MONTHS, SURFACE_TYPES, out_path
from step9_reduce_frostbite import BIN_EDGES, CLASSES, FT_EDGES, OVER_120, UNDEFINED

SCRIPT = "step11_level2_coverages.py"
FB_NOTE = ("Time to frostbite of exposed, dry cheek skin from ERA5 hourly 2 m air temperature and 10 m wind speed "
           "with TR-26-5 Eq. 5 (Nelson et al. 2002), as published (wind in mph x 8/5). Danger levels follow "
           "TR-26-5 Table 4: red FT <= 5 min, amber ('increased', orange in the report) 5 < FT <= 45, green "
           "('slight') 45 < FT <= 120. Eq. 5 does not reproduce every value of TR-26-5 Table 5 (see preprocess/README.md).")
CLASS_LONG = {"red": "great danger (red): frostbite in 5 minutes or less",
              "amber": "increased danger (amber/orange): frostbite in more than 5 and up to 45 minutes",
              "green": "slight danger (green): frostbite in more than 45 and up to 120 minutes",
              "none": "no frostbite danger: frostbite takes over 120 minutes, or air temperature is at or above "
                      "23.36 degF (-4.8 degC) where Eq. 5 gives no frostbite"}


def surface_type():
    with xr.open_dataset(INTERMEDIATE / "surface_type.nc") as st:
        return st["surface_type"].values


def add_surface_type(ds, st):
    cnt = {SURFACE_TYPES[k]: int((st == k).sum()) for k in SURFACE_TYPES}
    ds["surface_type"] = (("lat", "lon"), st.astype(np.int8), surface_type_attrs(cnt))
    return ds


def class_masks():
    """Boolean bin selectors per danger level, from the bin upper edges."""
    e = BIN_EDGES
    sel = {c: (e > lo) & (e <= hi) for c, (lo, hi) in CLASSES.items()}
    sel["none"] = e >= OVER_120
    assert sum(s.astype(int) for s in sel.values()).tolist() == [1] * len(e)
    return sel


def load_frostbite():
    counts, ft_min = [], []
    for m, d in DAYS:
        f = INTERMEDIATE / "frostbite" / f"{m}_{d:02d}.nc"
        if not f.exists():
            raise SystemExit(f"step 9 output missing: {f}")
        with xr.open_dataset(f) as ds:
            if not np.array_equal(ds["bin"].values, BIN_EDGES.astype(np.float32)):
                raise ValueError(f"{f}: unexpected bins")
            counts.append(ds["counts"].values.astype(np.int32))
            ft_min.append(ds["ft_min"].values)
    return np.stack(counts), np.stack(ft_min)  # (182, bin, lat, lon), (182, lat, lon)


def frostbite_coverages():
    st = surface_type()
    counts, ft_min = load_frostbite()
    sel = class_masks()
    groups = {"daily": [[i] for i in range(len(DAYS))],
              "monthly": [[i for i, (m, _) in enumerate(DAYS) if m == mon] for mon in MONTHS],
              "seasonal": [list(range(len(DAYS)))]}
    for res, idx in groups.items():
        ds = add_time(base_dataset(f"frostbite danger levels ({res})", f"{res.capitalize()} climatology of hourly "
                                   f"frostbite danger, 1991-2020, Oct-Mar (Feb 29 excluded). {FB_NOTE}"), res)
        c = np.stack([counts[g].sum(axis=0) for g in idx])  # (n, bin, lat, lon)
        n = c.sum(axis=1)  # hours per cell (720 x days)
        dims = ("lat", "lon") if res == "seasonal" else ("time", "lat", "lon")
        squeeze = (lambda a: a[0]) if res == "seasonal" else (lambda a: a)
        within = "days" if res == "daily" else {"monthly": "months", "seasonal": "seasons"}[res]
        for cls in ("red", "amber", "green", "none"):
            share = c[:, sel[cls]].sum(axis=1) / n * 100.0
            ds[f"frostbite_{cls}_share"] = (dims, squeeze(share).astype(np.float32), {
                "long_name": f"share of hours with {CLASS_LONG[cls]}", "units": "%", "grid_mapping": "crs",
                "cell_methods": f"time: sum within {within} time: sum over years"})
        with warnings.catch_warnings():  # cells that never fall below 23.36 degF stay NaN
            warnings.simplefilter("ignore", RuntimeWarning)
            fmin = np.stack([np.nanmin(ft_min[g], axis=0) if len(g) > 1 else ft_min[g[0]] for g in idx])
        ds["frostbite_time_min"] = (dims, squeeze(fmin).astype(np.float32), {
            "long_name": "shortest time to frostbite in any hour of 30 years (true minimum)", "units": "min",
            "grid_mapping": "crs", "cell_methods": f"time: minimum within {within} time: minimum over years",
            "comment": "NaN where air temperature never fell below 23.36 degF (-4.8 degC). 0 = the wind exceeded "
                       "~76 mph, beyond the range of Eq. 5 (counted as red)."})
        ds = add_surface_type(ds, st)
        dest = out_path("coverages", f"azcot_frostbite_{res}.nc")
        ds.to_netcdf(dest, encoding=encoding(finalize(ds, SCRIPT), chunks=True))
        print("wrote", dest, flush=True)

    ds = add_time(base_dataset("frostbite-time histograms (monthly)",
                               "Hours per frostbite-time bin, by month, 1991-2020 Oct-Mar (Feb 29 excluded). Sum over "
                               f"time for the whole season. {FB_NOTE}"), "monthly")
    ds = ds.assign_coords(bin=("bin", BIN_EDGES.astype(np.float32), {
        "long_name": "bin upper edge u in minutes: the bin holds hours with previous edge < FT <= u (the first bin "
                     f"starts at 0). {OVER_120:g} = FT over 120 min; {UNDEFINED:g} = no frostbite (air at or above "
                     "23.36 degF)", "units": "min"}))
    mc = np.stack([counts[g].sum(axis=0) for g in groups["monthly"]]).astype(np.int16)
    ds["frostbite_hour_counts"] = (("time", "bin", "lat", "lon"), mc, {
        "long_name": "number of hours per frostbite-time bin", "units": "1", "grid_mapping": "crs",
        "comment": "Share of hours with FT <= X minutes (X a bin edge): sum(counts[bin <= X]) / n_hours."})
    ds["n_hours"] = (("time",), mc.sum(axis=1)[:, 0, 0].astype(np.int32),
                     {"long_name": "hours per month in the 30-year pool"})
    ds = add_surface_type(ds, st)
    enc = encoding(finalize(ds, SCRIPT))
    enc["frostbite_hour_counts"] = {"zlib": True, "complevel": 2, "chunksizes": (1, 1, len(LAT), len(LON))}
    dest = out_path("coverages", "azcot_frostbite_histogram_monthly.nc")
    ds.to_netcdf(dest, encoding=enc)
    print("wrote", dest, flush=True)


SF_NOTE = ("Snowfall load = ERA5 hourly snowfall (m water equivalent) x 204.724 lb/ft2 per m (TR-26-5 eq. 4), read in "
           "place from the SNAP ERA5 holdings. 24-hour load: trailing 24-hour sum. Storm (a definition we chose; "
           "TR-26-5 gives none, see preprocess/storm_definition/README.md): wet hours (>= {wet} mm w.e./h) with dry gaps "
           "of at most {gap} h; storm total = all snowfall from its first to its last wet hour, credited to the day it "
           "ends. Not masked: snowfall over glaciers and sea ice is real (see surface_type).")
STORM_COMMENT = ("Storm definition (ours; TR-26-5 gives none): a run of hours with snowfall >= {wet} mm water "
                 "equivalent in which no dry gap exceeds {gap} h; total = all snowfall from the first to the last wet "
                 "hour, credited to the day the storm ends. In snowy maritime climates the result depends strongly on "
                 "the gap (e.g. Tromso record 14.9 / 30.9 / 36.8 lbf ft-2 for 6 / 12 / 24 h). See "
                 "preprocess/storm_definition/README.md; sf72_* is a definition-free cross-check.")
SF72_COMMENT = ("Largest trailing 72-hour snowfall load: a storm measure that needs no storm definition, kept as a "
                "cross-check on storm_* (see preprocess/storm_definition/README.md).")
SF24_EDGES = np.round(np.arange(0.5, 40.01, 0.5), 2)  # bin upper edges, lb/ft2; last bin open-ended
STORM_EDGES = np.arange(1.0, 80.01, 1.0)


def load_snowfall():
    """Stacks (30 years, 182 days, lat, lon) of sf24_daymax, storm_max and sf72_daymax, plus the step-10 parameters."""
    from config import DAYS, MONTH_NUM, YEARS
    day_idx = {(MONTH_NUM[m], d): i for i, (m, d) in enumerate(DAYS)}
    shape = (len(YEARS), len(DAYS), len(LAT), len(LON))
    sf24 = np.full(shape, np.nan, np.float32)
    storm = np.full(shape, np.nan, np.float32)
    sf72 = np.full(shape, np.nan, np.float32)
    params = None
    for Y in range(YEARS[0] - 1, YEARS[-1] + 1):
        f = INTERMEDIATE / "snowfall" / f"winter_{Y}.nc"
        if not f.exists():
            raise SystemExit(f"step 10 output missing: {f}")
        with xr.open_dataset(f) as ds:
            p = (float(ds.attrs["wet_mm_per_hour"]), int(ds.attrs["gap_hours"]))
            if params not in (None, p):
                raise ValueError(f"{f}: storm parameters {p} differ from {params}")
            params = p
            a24, ast, a72 = ds["sf24_daymax"].values, ds["storm_max"].values, ds["sf72_daymax"].values
            for k, t in enumerate(ds["date"].values.astype("datetime64[D]").astype(object)):
                sf24[t.year - YEARS[0], day_idx[(t.month, t.day)]] = a24[k]
                storm[t.year - YEARS[0], day_idx[(t.month, t.day)]] = ast[k]
                sf72[t.year - YEARS[0], day_idx[(t.month, t.day)]] = a72[k]
    if np.isnan(sf24).any() or np.isnan(storm).any() or np.isnan(sf72).any():
        raise ValueError("snowfall stacks incomplete (some year/day missing)")
    return sf24, storm, sf72, params


def snowfall_coverages():
    from config import DAYS
    st = surface_type()
    sf24, storm, sf72, (wet, gap) = load_snowfall()
    note = SF_NOTE.format(wet=wet, gap=gap)
    groups = {"daily": [[i] for i in range(len(DAYS))],
              "monthly": [[i for i, (m, _) in enumerate(DAYS) if m == mon] for mon in MONTHS],
              "seasonal": [list(range(len(DAYS)))]}
    for res, idx in groups.items():
        ds = add_time(base_dataset(f"snowfall loads ({res})", f"{res.capitalize()} climatology of 24-hour and storm-total "
                                   f"snowfall loads, 1991-2020, Oct-Mar (Feb 29 excluded). {note}"), res)
        dims = ("lat", "lon") if res == "seasonal" else ("time", "lat", "lon")
        sq = (lambda a: a[0]) if res == "seasonal" else (lambda a: a)
        within = "days" if res == "daily" else {"monthly": "months", "seasonal": "seasons"}[res]
        out = {}
        for name, arr, limit, label in (("sf24", sf24, 10.0, "24-hour snowfall load"),
                                        ("storm", storm, 20.0, "storm-total snowfall load"),
                                        ("sf72", sf72, None, "72-hour snowfall load")):
            ann = np.stack([arr[:, g].max(axis=1) for g in idx], axis=1)  # (30, n, lat, lon) yearly max per period
            out[f"{name}_max"] = (ann.max(axis=0), {
                "long_name": f"highest {label} in 30 years (record)", "units": "lbf ft-2",
                "cell_methods": f"time: maximum within {within} time: maximum over years"})
            out[f"{name}_mean_annual_max"] = (ann.mean(axis=0), {
                "long_name": f"mean over 30 years of each year's highest {label}", "units": "lbf ft-2",
                "cell_methods": f"time: maximum within {within} time: mean over years"})
            if limit is None:
                continue
            key = "sf24_ge10_years" if name == "sf24" else "storm_ge20_years"
            what = "tentage criterion" if name == "sf24" else "rigid-shelter criterion"
            out[key] = ((ann >= limit).mean(axis=0) * 100.0, {
                "long_name": f"share of years with a {label} >= {limit:g} lbf ft-2 ({what}, TR-26-5)", "units": "%"})
            if res != "daily":
                n = np.stack([(arr[:, g] >= limit).sum(axis=1) for g in idx], axis=1).mean(axis=0)
                key = "sf24_ge10_days" if name == "sf24" else "storm_ge20_per_year"
                long = (f"mean days per year whose highest 24-hour snowfall load is >= {limit:g} lbf ft-2"
                        if name == "sf24" else f"mean storms per year with a total >= {limit:g} lbf ft-2")
                out[key] = (n, {"long_name": long, "units": "days" if name == "sf24" else "1"})
        for k, (a, attrs) in out.items():
            if k.startswith("storm"):
                attrs = dict(attrs, comment=STORM_COMMENT.format(wet=wet, gap=gap))
            elif k.startswith("sf72"):
                attrs = dict(attrs, comment=SF72_COMMENT)
            ds[k] = (dims, sq(a).astype(np.float32), dict(attrs, grid_mapping="crs"))
        ds = add_surface_type(ds, st)
        dest = out_path("coverages", f"azcot_snowfall_{res}.nc")
        ds.to_netcdf(dest, encoding=encoding(finalize(ds, SCRIPT), chunks=True))
        print("wrote", dest, flush=True)

    ds = add_time(base_dataset("snowfall-load histograms (monthly)",
                               "Days per bin of the day's highest 24-hour snowfall load, and storms per bin of storm "
                               f"total, by month, 1991-2020 Oct-Mar (Feb 29 excluded). {note}"), "monthly")
    ds = ds.assign_coords(
        sf24_bin=("sf24_bin", SF24_EDGES.astype(np.float32), {
            "long_name": "bin upper edge u: days with previous edge < load <= u (first bin from 0; last open-ended)",
            "units": "lbf ft-2"}),
        storm_bin=("storm_bin", STORM_EDGES.astype(np.float32), {
            "long_name": "bin upper edge u: storms with previous edge < total <= u (first bin from 0; last open-ended)",
            "units": "lbf ft-2"}))
    days24, storms = [], []
    for g in groups["monthly"]:
        a = sf24[:, g].reshape(-1, len(LAT), len(LON))
        b = storm[:, g].reshape(-1, len(LAT), len(LON))
        ia = np.clip(np.searchsorted(SF24_EDGES, a, side="left"), 0, len(SF24_EDGES) - 1)
        ib = np.clip(np.searchsorted(STORM_EDGES, b, side="left"), 0, len(STORM_EDGES) - 1)
        days24.append(np.stack([(ia == k).sum(axis=0) for k in range(len(SF24_EDGES))]))
        storms.append(np.stack([((ib == k) & (b > 0)).sum(axis=0) for k in range(len(STORM_EDGES))]))
    ds["sf24_day_counts"] = (("time", "sf24_bin", "lat", "lon"), np.stack(days24).astype(np.int16), {
        "long_name": "number of days per bin of the day's highest 24-hour snowfall load", "units": "1",
        "grid_mapping": "crs", "comment": "% of days with load > X: sum(counts[sf24_bin > X]) / n_days * 100"})
    ds["storm_counts"] = (("time", "storm_bin", "lat", "lon"), np.stack(storms).astype(np.int16), {
        "long_name": "number of storms per bin of storm-total snowfall load, by month of storm end", "units": "1",
        "grid_mapping": "crs", "comment": "storms per year with total > X: sum(counts[storm_bin > X]) / 30. "
                                          + STORM_COMMENT.format(wet=wet, gap=gap)})
    ds["n_days"] = (("time",), np.array([len(g) * 30 for g in groups["monthly"]], np.int32),
                    {"long_name": "days per month in the 30-year pool"})
    ds = add_surface_type(ds, st)
    enc = encoding(finalize(ds, SCRIPT))
    for v in ("sf24_day_counts", "storm_counts"):
        enc[v] = {"zlib": True, "complevel": 2, "chunksizes": (1, 1, len(LAT), len(LON))}
    dest = out_path("coverages", "azcot_snowfall_histogram_monthly.nc")
    ds.to_netcdf(dest, encoding=enc)
    print("wrote", dest, flush=True)


def main():
    import sys
    which = sys.argv[1:] or ["frostbite", "snowfall"]
    if "frostbite" in which:
        frostbite_coverages()
    if "snowfall" in which:
        snowfall_coverages()


if __name__ == "__main__":
    main()
