"""Stack selected fields from the 183 daily Metrics files into (day, lat, lon) cubes.

Outputs (git-ignored) in eda/cache/:
  wct_daily.nc, sl_daily.nc  - one variable per selected metric, dims (day, g0_lat_0, g0_lon_1)
  masks.nc                   - land (from ERA5-Land SD NaNs) and glacier/perennial-snow masks

Source files are opened read-only and never modified.
"""
import sys
import time
from multiprocessing import Pool

import numpy as np
import xarray as xr

from azcot import CACHE, DAYS, SL_GLACIER_CAP, open_daily

SELECT = {
    "WCT": ["averageTemp", "min_WCT", "percentile_1", "percentile_5", "percentile_50",
            "frequency_0", "frequency_-20", "frequency_-40", "frequency_-65",
            "consecutive_-20", "consecutive_-40"],
    "SL": ["averageSL", "max_SL", "percentile_50", "percentile_95",
           "frequency_10", "frequency_20", "frequency_25", "frequency_50"],
}


def read_day(args):
    var, (m, d) = args
    with open_daily(var, m, d) as ds:
        return {v: ds[v].values.astype(np.float32) for v in SELECT[var]}


def build(var, workers):
    t0 = time.time()
    with Pool(workers) as pool:
        days = pool.map(read_day, [(var, md) for md in DAYS], chunksize=4)
    with open_daily(var, *DAYS[0]) as ref:
        coords = {"g0_lat_0": ref.g0_lat_0.values, "g0_lon_1": ref.g0_lon_1.values}
    labels = [f"{m}_{d:02d}" for m, d in DAYS]
    out = xr.Dataset(
        {v: (("day", "g0_lat_0", "g0_lon_1"), np.stack([dd[v] for dd in days])) for v in SELECT[var]},
        coords={"day": labels, **coords},
        attrs={"source": f"disk1/Metrics/daily_{var}_stats", "note": "stacked by eda/scripts/build_cubes.py"},
    )
    enc = {v: {"zlib": True, "complevel": 1} for v in out.data_vars}
    out.to_netcdf(CACHE / f"{var.lower()}_daily.nc", encoding=enc)
    print(f"{var}: {len(days)} days, {len(SELECT[var])} vars in {time.time() - t0:.0f}s", flush=True)
    return out


def build_masks(sl):
    with open_daily("SD", "jan", 15) as sd:
        sdv = sd[list(sd.data_vars)[0]]
        lat_name, lon_name = sdv.dims
        on_grid = sdv.sel({lat_name: sl.g0_lat_0.values, lon_name: sl.g0_lon_1.values}, method="nearest")
        land = xr.DataArray(np.isfinite(on_grid.values), dims=("g0_lat_0", "g0_lon_1"),
                            coords={"g0_lat_0": sl.g0_lat_0, "g0_lon_1": sl.g0_lon_1})
    # Perennial snow / ice: real seasonal snowpack is near zero on Oct 1, and ERA5 caps
    # snow over permanent ice at ~10 m w.e. Flag cells already carrying a large load on
    # Oct 1, or that ever touch the cap.
    oct1 = sl["averageSL"].isel(day=0)
    seasonmax = sl["max_SL"].max("day")
    glacier = (oct1 > 50) | (seasonmax > 0.95 * SL_GLACIER_CAP)
    masks = xr.Dataset({"land": land, "glacier": glacier & land, "oct1_SL": oct1, "season_max_SL": seasonmax})
    masks.to_netcdf(CACHE / "masks.nc")
    print(f"masks: land {float(land.mean()) * 100:.1f}% of cells, glacier {float(masks.glacier.mean()) * 100:.1f}%",
          flush=True)


if __name__ == "__main__":
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    CACHE.mkdir(exist_ok=True)
    sl = build("SL", workers)
    build_masks(sl)
    build("WCT", workers)
    print("DONE", flush=True)
