"""Step 3: climatology coverages (min of min, mean of mean, max of max) at daily, monthly, seasonal resolution.

Inputs: step-1 per-day intermediates and step-2 surface_type.
Outputs (coverages/):
    azcot_{wct,sl}_climatology_{daily,monthly,seasonal}.nc
Daily values are the true min / mean / max of the 720 hourly values (30 years x 24 h) for each calendar day.
Monthly and seasonal values aggregate those days: min of daily mins, mean of daily means (every day has
720 hours, so this equals the mean of all hours), max of daily maxes.
Snow load is NaN wherever surface_type != 1 (land); see surface_type for ocean / glacier / perennial snow.
"""
import numpy as np
import xarray as xr

from cf import add_time, base_dataset, encoding, finalize, surface_type_attrs
from config import DAYS, INTERMEDIATE, MONTH_NUM, MONTHS, SURFACE_TYPES, out_path

VARS = {
    "wct": {"name": "wind chill temperature", "units": "degF",
            "note": "NWS 2001 wind chill (Nelson et al. 2002) from ERA5 2 m temperature and 10 m wind speed."},
    "sl": {"name": "snow load", "units": "lbf ft-2",
           "note": "Snow load on a flat surface, SL = SWE[in] x 5.2 (TR-26-5 eq. 4), from ERA5 snow depth (m w.e.)."},
    # Added by step 7 (built from step-6 intermediates):
    "t2": {"name": "2 m air temperature", "units": "degF", "note": "ERA5 2 m temperature (K converted to degF)."},
    "wspd": {"name": "10 m wind speed", "units": "knots",
             "note": "ERA5 10 m wind speed, hourly mean (no gusts); the raw '*_knots.nc' files are m/s, converted here."},
    "sd": {"name": "snow depth", "units": "inches",
           "note": "ERA5-Land snow depth on its native 0.1-degree grid (m converted to inches); NaN over water."},
}
STAT_WORDS = {"min": ("minimum", "lowest"), "mean": ("mean", "mean"), "max": ("maximum", "highest")}
SCOPE = {"daily": "days", "monthly": "months", "seasonal": "seasons"}


def load_days(var):
    files = [INTERMEDIATE / "hourly_reduce" / var / f"{m}_{d:02d}.nc" for m, d in DAYS]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise SystemExit(f"step 1 {var} output missing for {len(missing)} days, e.g. {missing[:3]}")
    out = {s: [] for s in ("min", "mean", "max")}
    for f in files:
        with xr.open_dataset(f) as ds:
            if ds.attrs["n_hours"] + ds.attrs.get("n_missing_hours", 0) != 720:
                raise ValueError(f"{f} built from {ds.attrs['n_hours']} hours")
            for s in out:
                out[s].append(ds[s].values)
    return {s: np.stack(v) for s, v in out.items()}  # (182, lat, lon)


def aggregate(stack, stat, groups):
    fn = {"min": np.min, "mean": np.mean, "max": np.max}[stat]
    return np.stack([fn(stack[idx], axis=0) for idx in groups])


def build(var, stacks, surface_type, resolution, grid=None, extra=None, script="step3_climatology.py"):
    """surface_type=None for variables on another grid (SD); `extra` adds {name: (dims, array, attrs)}."""
    meta = VARS[var]
    ds = base_dataset(f"{meta['name']} climatology ({resolution})",
                      f"{resolution.capitalize()} climatology of hourly ERA5 {meta['name']}, 1991-2020, Oct-Mar. "
                      f"{meta['note']}", *(grid or ()))
    ds = add_time(ds, resolution)
    if resolution == "daily":
        groups = None
    elif resolution == "monthly":
        groups = [[i for i, (m, _) in enumerate(DAYS) if m == mon] for mon in MONTHS]
    else:
        groups = [list(range(len(DAYS)))]
    land = None if surface_type is None else surface_type == 1
    for stat in ("min", "mean", "max"):
        arr = stacks[stat] if groups is None else aggregate(stacks[stat], stat, groups)
        if var == "sl":
            arr = np.where(land, arr, np.nan)
        dims = ("lat", "lon") if resolution == "seasonal" else ("time", "lat", "lon")
        if resolution == "seasonal":
            arr = arr[0]
        word, adj = STAT_WORDS[stat]
        within = "days" if resolution == "daily" else SCOPE[resolution]
        cm = (f"time: {word} within days time: {word} over years" if resolution == "daily"
              else f"time: {word} within {within} time: {word} over years")
        if stat == "mean":
            long = f"mean hourly {meta['name']}"
        else:
            long = f"{adj} hourly {meta['name']} in 30 years (true {word}, not a mean of annual {word}s)"
        ds[f"{var}_{stat}"] = (dims, arr.astype(np.float32), {
            "long_name": long, "units": meta["units"], "grid_mapping": "crs", "cell_methods": cm,
            **({"comment": "NaN where surface_type != 1 (ocean, glacier, perennial snow)"} if var == "sl" else {})})
    for name, (dims, arr, attrs) in (extra or {}).items():
        ds[name] = (dims, arr.astype(np.float32), dict(attrs, grid_mapping="crs"))
    if surface_type is not None:
        counts = {SURFACE_TYPES[k]: int((surface_type == k).sum()) for k in SURFACE_TYPES}
        ds["surface_type"] = (("lat", "lon"), surface_type.astype(np.int8), surface_type_attrs(counts))
    dest = out_path("coverages", f"azcot_{var}_climatology_{resolution}.nc")
    ds.to_netcdf(dest, encoding=encoding(finalize(ds, script), chunks=True))
    print("wrote", dest, flush=True)


def main():
    with xr.open_dataset(INTERMEDIATE / "surface_type.nc") as st:
        surface_type = st["surface_type"].values
    for var in ("wct", "sl"):
        stacks = load_days(var)
        for res in ("daily", "monthly", "seasonal"):
            build(var, stacks, surface_type, res)


if __name__ == "__main__":
    main()
