"""Step 2: build the surface_type flag (0 ocean, 1 land, 2 glacier, 3 perennial snow).

Inputs: step-1 SL intermediates (true hourly min/mean/max per day) and the ERA5-Land snow-depth grid
in disk1/Metrics/daily_SD_stats (NaN over water = not land).
Output: intermediate/surface_type.nc

Rules (evidence in preprocess/README.md):
  glacier (2)        SL min over every hour of all 182 days >= GLACIER_FRACTION * the 10 m w.e. cap,
                     i.e. ERA5 holds the cell at its constant glacier snow mass all season.
  perennial snow (3) not glacier, and the LOWEST hour on Oct 1 across all 30 years is still
                     >= PERENNIAL_SL lb/ft2: snow that survived every summer, accumulating without limit
                     until it reaches the cap. Not a seasonal snow load.
  land (1)           ERA5-Land land cell, OR any cell with snow in any hour (ERA5 only carries snow on its own
                     land points; ~5,700 coastal cells have ERA5 snow but fall on water in the 0.1-deg ERA5-Land
                     mask), that is neither of the above.
  ocean (0)          everything else.
"""
import numpy as np
import xarray as xr

from config import DAYS, GLACIER_SL, INTERMEDIATE, LAT, LON, SURFACE_TYPES, metrics_daily, out_path

GLACIER_FRACTION = 0.999
PERENNIAL_SL = 50.0  # lb/ft2 (~0.24 m w.e.) on the least-snowy hour of Oct 1 across all 30 years


def land_mask():
    with xr.open_dataset(metrics_daily("SD", "jan", 15)) as sd:  # ERA5-Land 0.1 deg, NaN over water
        v = sd[list(sd.data_vars)[0]]
        lat_name, lon_name = v.dims
        on_grid = v.sel({lat_name: LAT, lon_name: LON}, method="nearest", tolerance=0.06)
        return np.isfinite(on_grid.values)


def main():
    files = [INTERMEDIATE / "hourly_reduce" / "sl" / f"{m}_{d:02d}.nc" for m, d in DAYS]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise SystemExit(f"step 1 SL output missing for {len(missing)} days, e.g. {missing[:3]}")
    season_min = season_max = None
    for f in files:
        with xr.open_dataset(f) as ds:
            lo, hi = ds["min"].values, ds["max"].values
        season_min = lo if season_min is None else np.minimum(season_min, lo)
        season_max = hi if season_max is None else np.maximum(season_max, hi)
    with xr.open_dataset(files[0]) as oct1:
        oct1_min = oct1["min"].values

    era5land = land_mask()
    land = era5land | (season_max > 0)
    print(f"land: {int(era5land.sum())} ERA5-Land cells + {int((land & ~era5land).sum())} cells with ERA5 snow")
    glacier = season_min >= GLACIER_FRACTION * GLACIER_SL
    perennial = ~glacier & (oct1_min >= PERENNIAL_SL)
    st = np.zeros(land.shape, np.int8)
    st[land] = 1
    st[perennial] = 3
    st[glacier] = 2
    counts = {SURFACE_TYPES[k]: int((st == k).sum()) for k in SURFACE_TYPES}
    print("surface_type counts:", counts)
    print("glacier cells outside ERA5-Land mask:", int((glacier & ~land).sum()),
          "| perennial outside land:", int((perennial & ~land).sum()))

    ds = xr.Dataset(
        {"surface_type": (("lat", "lon"), st),
         "season_min_sl": (("lat", "lon"), season_min.astype(np.float32),
                           {"units": "lbf ft-2", "long_name": "lowest hourly snow load, Oct-Mar 1991-2020"}),
         "oct1_min_sl": (("lat", "lon"), oct1_min.astype(np.float32),
                         {"units": "lbf ft-2", "long_name": "lowest hourly snow load on Oct 1, 1991-2020"}),
         "season_max_sl": (("lat", "lon"), season_max.astype(np.float32),
                           {"units": "lbf ft-2", "long_name": "highest hourly snow load, Oct-Mar 1991-2020"}),
         "era5land_mask": (("lat", "lon"), era5land.astype(np.int8),
                           {"long_name": "1 where ERA5-Land snow depth is defined (land)"})},
        coords={"lat": LAT, "lon": LON},
        attrs={"glacier_rule": f"season_min_sl >= {GLACIER_FRACTION} * {GLACIER_SL:.3f}",
               "perennial_rule": f"not glacier and oct1_min_sl >= {PERENNIAL_SL}",
               "land_rule": ("finite ERA5-Land snow depth (disk1/Metrics/daily_SD_stats/jan_15, nearest 0.1->0.25 deg) "
                             "OR season_max_sl > 0"),
               "counts": str(counts)})
    ds.to_netcdf(out_path("intermediate", "surface_type.nc"))


if __name__ == "__main__":
    main()
