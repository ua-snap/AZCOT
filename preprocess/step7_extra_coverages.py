"""Step 7: coverages for air temperature (t2), wind speed (wspd) and snow depth (sd) from the step-6 intermediates.

Outputs (coverages/):
    azcot_{t2,wspd,sd}_climatology_{daily,monthly,seasonal}.nc   min of min / mean of mean / max of max, as in step 3.
                                                                 t2 monthly/seasonal also carry t2_freeze_thaw_days.
    azcot_{t2,wspd,sd}_histogram_monthly.nc                      counts of hourly values per unit bin and month
                                                                 (sum over `time` for the season). Any frequency
                                                                 ("% of hours <= T") or percentile at 1-unit
                                                                 resolution follows from these.
t2 and wspd are on the 0.25-degree ERA5 grid with surface_type; sd stays on the 0.1-degree ERA5-Land grid (NaN over
water, no surface_type). The Metrics 2T and WSPD threshold statistics are NOT used: Metrics 2T is in kelvin with degF
thresholds; Metrics max_WSPD is a copy of min_WS10 (see README).
"""
import numpy as np
import xarray as xr

from cf import add_time, base_dataset, encoding, finalize, surface_type_attrs
from config import INTERMEDIATE, LAT, LON, MONTHS, SD_LAT, SD_LON, SURFACE_TYPES, out_path
from step3_climatology import build, load_days

GRIDS = {"t2": (LAT, LON), "wspd": (LAT, LON), "sd": (SD_LAT, SD_LON)}
HIST_NOTE = {
    "t2": "2 m air temperature, degF",
    "wspd": "10 m wind speed (hourly mean), knots",
    "sd": "snow depth, inches",
}


def freeze_thaw():
    per_month = []
    for m in MONTHS:
        with xr.open_dataset(INTERMEDIATE / "freeze_thaw" / f"t2_{m}.nc") as f:
            per_month.append(f["freeze_thaw_days"].values)
    return np.stack(per_month)  # (6, lat, lon) days per year


def histogram_coverage(var, surface_type):
    lat, lon = GRIDS[var]
    ds = base_dataset(f"{HIST_NOTE[var]} hourly-value histograms (monthly)",
                      f"Counts of hourly {HIST_NOTE[var]} values per unit bin, by month, 1991-2020 Oct-Mar "
                      "(Feb 29 excluded). Sum over time for the whole season.", lat, lon)
    ds = add_time(ds, "monthly")
    counts, n_hours = [], []
    for m in MONTHS:
        with xr.open_dataset(INTERMEDIATE / "histograms" / f"{var}_{m}.nc") as h:
            counts.append(h["counts"].values.astype(np.int16))
            n_hours.append(int(h.attrs["n_hours"]))
            bins = h["bin"].values
    ds = ds.assign_coords(bin=("bin", bins, {
        "long_name": "bin upper edge u; the bin holds hours with u-1 < value <= u (first and last bins open-ended)",
        "units": {"t2": "degF", "wspd": "knots", "sd": "inches"}[var]}))
    ds[f"{var}_hour_counts"] = (("time", "bin", "lat", "lon"), np.stack(counts), {
        "long_name": f"number of hours per value bin ({HIST_NOTE[var]})", "units": "1", "grid_mapping": "crs",
        "comment": "Share of hours with value <= T: sum(counts[bin <= T]) / n_hours. Cells without data are all 0."})
    ds["n_hours"] = (("time",), np.array(n_hours, np.int32), {"long_name": "hours per month in the 30-year pool"})
    if surface_type is not None:
        cnt = {SURFACE_TYPES[k]: int((surface_type == k).sum()) for k in SURFACE_TYPES}
        ds["surface_type"] = (("lat", "lon"), surface_type.astype(np.int8), surface_type_attrs(cnt))
    enc = encoding(ds)
    enc[f"{var}_hour_counts"] = {"zlib": True, "complevel": 2, "chunksizes": (1, 1, len(lat), len(lon))}
    dest = out_path("coverages", f"azcot_{var}_histogram_monthly.nc")
    ds.to_netcdf(dest, encoding=enc)
    print("wrote", dest, flush=True)


def main():
    with xr.open_dataset(INTERMEDIATE / "surface_type.nc") as st:
        surface_type = st["surface_type"].values
    ft = freeze_thaw()
    ft_attrs = {"long_name": "freeze-thaw days per year (hourly 2T both below and above 32 degF on the same day)",
                "units": "days"}
    for var in ("t2", "wspd", "sd"):
        stacks = load_days(var)
        st = None if var == "sd" else surface_type
        for res in ("daily", "monthly", "seasonal"):
            extra = None
            if var == "t2" and res == "monthly":
                extra = {"t2_freeze_thaw_days": (("time", "lat", "lon"), ft, ft_attrs)}
            elif var == "t2" and res == "seasonal":
                extra = {"t2_freeze_thaw_days": (("lat", "lon"), ft.sum(axis=0), ft_attrs)}
            build(var, stacks, st, res, grid=GRIDS[var], extra=extra, script="step7_extra_coverages.py")
        del stacks
        histogram_coverage(var, st)


if __name__ == "__main__":
    main()
