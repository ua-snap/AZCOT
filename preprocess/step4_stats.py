"""Step 4: threshold / percentile stats coverages from disk1/Metrics (Feb 29 dropped).

Outputs (coverages/):
    azcot_wct_stats_{daily,monthly,seasonal}.nc  wct_frequency, wct_consecutive, wct_consecutive_no_ones,
                                                 wct_percentile (daily only)
    azcot_sl_stats_{daily,monthly,seasonal}.nc   sl_frequency, sl_percentile (daily only)
Monthly and seasonal frequency / consecutive values are means of the daily values. That is exact for
frequency (every day has 720 hours) and matches how the Atlas aggregated consecutive. Percentiles can't be
averaged across days, so they exist only at daily resolution.
These Metrics fields were verified against the raw hourly data (see eda/EDA.md section 2).
"""
import argparse
import os
from multiprocessing import Pool

import numpy as np
import xarray as xr

from cf import add_time, base_dataset, encoding, finalize, surface_type_attrs
from config import DAYS, INTERMEDIATE, LAT, LON, MONTHS, SURFACE_TYPES, metrics_daily, out_path

SPEC = {
    "WCT": {
        "frequency": ("frequency_{}", list(range(0, -101, -5)), "wct_threshold"),
        "consecutive": ("consecutive_{}", list(range(0, -76, -5)), "wct_consec_threshold"),
        "consecutive_no_ones": ("consecutive_{}_no_ones", list(range(0, -76, -5)), "wct_consec_threshold"),
        "percentile": ("percentile_{}", [1, 5, 10, 15, 20, 25, 50], "percentile"),
    },
    "SL": {
        "frequency": ("frequency_{}", list(range(0, 51, 5)), "sl_threshold"),
        "percentile": ("percentile_{}", [50, 75, 80, 85, 90, 95, 99], "percentile"),
    },
}
ATTRS = {
    ("WCT", "frequency"): {"long_name": "share of hours with wind chill at or below threshold", "units": "%"},
    ("WCT", "consecutive"): {
        "long_name": "mean length of runs with wind chill at or below threshold within each UTC day",
        "units": "hours",
        "comment": ("For each year: mean length of runs (hours) with WCT <= threshold inside the 24 UTC hours of the "
                    "day, 0 if none; then averaged over 30 years. Because no-event years count as 0, this mixes how "
                    "often spells occur with how long they last. Runs are cut at 00 UTC.")},
    ("WCT", "consecutive_no_ones"): {
        "long_name": "as wct_consecutive, ignoring 1-hour runs", "units": "hours"},
    ("WCT", "percentile"): {"long_name": "percentile of hourly wind chill (pandas linear interpolation)",
                            "units": "degF"},
    ("SL", "frequency"): {"long_name": "share of hours with snow load at or above threshold", "units": "%"},
    ("SL", "percentile"): {"long_name": "percentile of hourly snow load (pandas linear interpolation)",
                           "units": "lbf ft-2"},
}
COORD_ATTRS = {
    "wct_threshold": {"long_name": "wind chill threshold (hour counted if WCT <= threshold)", "units": "degF"},
    "wct_consec_threshold": {"long_name": "wind chill threshold for consecutive runs (WCT <= threshold)",
                             "units": "degF"},
    "sl_threshold": {"long_name": "snow load threshold (hour counted if SL >= threshold)", "units": "lbf ft-2"},
    "percentile": {"long_name": "percentile of the 720 hourly values", "units": "percent"},
}


def read_day(args):
    var, m, d = args
    with xr.open_dataset(metrics_daily(var, m, d)) as ds:  # read-only
        if not (np.allclose(ds.g0_lat_0.values, LAT, atol=1e-3) and np.allclose(ds.g0_lon_1.values, LON, atol=1e-3)):
            raise ValueError(f"unexpected grid in {metrics_daily(var, m, d)}")
        return {k: np.stack([ds[pat.format(t)].values.astype(np.float32) for t in thr])
                for k, (pat, thr, _) in SPEC[var].items()}


def build(var, days, surface_type, resolution):
    lower = var.lower()
    ds = base_dataset(f"{'wind chill' if var == 'WCT' else 'snow load'} threshold statistics ({resolution})",
                      f"Threshold frequencies, persistence and percentiles from disk1/Metrics/daily_{var}_stats, "
                      "1991-2020 Oct-Mar, Feb 29 excluded.")
    ds = add_time(ds, resolution)
    land = surface_type == 1
    if resolution == "monthly":
        groups = [[i for i, (m, _) in enumerate(DAYS) if m == mon] for mon in MONTHS]
    elif resolution == "seasonal":
        groups = [list(range(len(DAYS)))]
    for key, (_, thr, dim) in SPEC[var].items():
        if key == "percentile" and resolution != "daily":
            continue
        stack = np.stack([day[key] for day in days])  # (time, thr, lat, lon)
        if resolution != "daily":
            stack = np.stack([stack[idx].mean(axis=0) for idx in groups])
        if var == "SL":
            stack = np.where(land, stack, np.nan)
        if resolution == "seasonal":
            stack, dims = stack[0], (dim, "lat", "lon")
        else:
            dims = ("time", dim, "lat", "lon")
        if dim not in ds.coords:
            ds = ds.assign_coords({dim: (dim, np.array(thr, np.float32), COORD_ATTRS[dim])})
        attrs = dict(ATTRS[(var, key)], grid_mapping="crs", source_variables=SPEC[var][key][0].format("<threshold>"))
        if resolution != "daily":
            attrs["cell_methods"] = f"time: mean over days (within {'months' if resolution == 'monthly' else 'Oct-Mar'})"
        if var == "SL":
            attrs["comment"] = (attrs.get("comment", "") + " NaN where surface_type != 1.").strip()
        ds[f"{lower}_{key}"] = (dims, stack.astype(np.float32), attrs)
    counts = {SURFACE_TYPES[k]: int((surface_type == k).sum()) for k in SURFACE_TYPES}
    ds["surface_type"] = (("lat", "lon"), surface_type.astype(np.int8), surface_type_attrs(counts))
    dest = out_path("coverages", f"azcot_{lower}_stats_{resolution}.nc")
    ds.to_netcdf(dest, encoding=encoding(finalize(ds, "step4_stats.py"), chunks=True))
    print("wrote", dest, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", 4)))
    args = ap.parse_args()
    with xr.open_dataset(INTERMEDIATE / "surface_type.nc") as st:
        surface_type = st["surface_type"].values
    for var in SPEC:
        with Pool(args.workers) as pool:
            days = pool.map(read_day, [(var, m, d) for m, d in DAYS])
        for res in ("daily", "monthly", "seasonal"):
            build(var, days, surface_type, res)
        del days


if __name__ == "__main__":
    main()
