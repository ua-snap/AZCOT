"""CF-1.8 metadata helpers shared by the coverage builders."""
import datetime as dt

import numpy as np
import xarray as xr

from config import (DAYS, GLACIER_SL, GLOBAL_ATTRS, LAT, LON, MONTH_NUM, MONTHS, NOMINAL_DATES, NOMINAL_MONTHS,
                    SURFACE_TYPES)

WKT_4326 = ('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],'
            'UNIT["degree",0.0174532925199433],AXIS["Latitude",NORTH],AXIS["Longitude",EAST],AUTHORITY["EPSG","4326"]]')
TIME_UNITS = "days since 2001-10-01 00:00:00"
FILL = np.float32(np.nan)


def crs_var():
    return xr.DataArray(np.int32(0), attrs={
        "grid_mapping_name": "latitude_longitude", "semi_major_axis": 6378137.0,
        "inverse_flattening": 298.257223563, "longitude_of_prime_meridian": 0.0,
        "crs_wkt": WKT_4326, "spatial_ref": WKT_4326, "epsg_code": "EPSG:4326"})


def base_dataset(title_suffix, summary, lat=LAT, lon=LON):
    ds = xr.Dataset(coords={
        "lat": ("lat", lat, {"standard_name": "latitude", "long_name": "latitude", "units": "degrees_north", "axis": "Y"}),
        "lon": ("lon", lon, {"standard_name": "longitude", "long_name": "longitude", "units": "degrees_east", "axis": "X"}),
    })
    res = f"{abs(float(lat[1] - lat[0])):g} degree"
    ds["crs"] = crs_var()
    ds.attrs = dict(GLOBAL_ATTRS, title=f"{GLOBAL_ATTRS['title']}: {title_suffix}", summary=summary,
                    date_created=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    geospatial_lat_min=float(lat.min()), geospatial_lat_max=float(lat.max()),
                    geospatial_lon_min=float(lon.min()), geospatial_lon_max=float(lon.max()),
                    geospatial_lat_resolution=res, geospatial_lon_resolution=res)
    return ds


def _days_since(date):
    return (np.datetime64(date) - np.datetime64("2001-10-01")).astype("timedelta64[D]").astype(float)


def add_time(ds, resolution):
    """Attach a climatological time axis: 'daily' (182, no Feb 29), 'monthly' (6), or 'seasonal' (none)."""
    if resolution == "seasonal":
        ds.attrs["time_coverage"] = "October-March of 1991-2020 (Feb 29 excluded), pooled into one field"
        return ds
    if resolution == "daily":
        t = np.array([_days_since(d) for d in NOMINAL_DATES.values])
        bounds = np.array([[_days_since(f"1991-{MONTH_NUM[m]:02d}-{d:02d}"),
                            _days_since(f"2020-{MONTH_NUM[m]:02d}-{d:02d}") + 1] for m, d in DAYS])
        extra = {"calendar_day": ("time", np.array([f"{m}_{d:02d}" for m, d in DAYS]),
                                  {"long_name": "calendar day of the climatology (mon_DD)"}),
                 "month": ("time", np.array([MONTH_NUM[m] for m, _ in DAYS], np.int8), {"long_name": "month"}),
                 "day": ("time", np.array([d for _, d in DAYS], np.int8), {"long_name": "day of month"})}
    else:
        t = np.array([_days_since(d) for d in NOMINAL_MONTHS.values])
        bounds = []
        for m in MONTHS:
            mm = MONTH_NUM[m]
            end = f"2020-{mm + 1:02d}-01" if mm < 12 else "2021-01-01"
            bounds.append([_days_since(f"1991-{mm:02d}-01"), _days_since(end)])
        bounds = np.array(bounds)
        extra = {"month": ("time", np.array([MONTH_NUM[m] for m in MONTHS], np.int8), {"long_name": "month"})}
    ds = ds.assign_coords(time=("time", t, {
        "standard_name": "time", "long_name": "nominal climatological date (non-leap reference season 2001-02)",
        "units": TIME_UNITS, "calendar": "standard", "axis": "T", "climatology": "climatology_bounds"}), **extra)
    ds["climatology_bounds"] = (("time", "nv"), bounds.astype(np.float64))
    return ds


def surface_type_attrs(n_by_class):
    return {
        "long_name": "ERA5 surface type for snow-load interpretation",
        "flag_values": np.array(list(SURFACE_TYPES), np.int8),
        "flag_meanings": " ".join(SURFACE_TYPES.values()),
        "grid_mapping": "crs",
        "comment": (
            "0 ocean: not land in ERA5-Land (snow depth NaN in disk1/Metrics/daily_SD_stats) and no ERA5 snow in "
            "any hour. "
            "1 land: ERA5-Land land or ERA5 snow in some hour, seasonal snow; snow load valid. "
            f"2 glacier: snow water equivalent held at the ERA5 glacier constant of 10 m (= {GLACIER_SL:.2f} lbf ft-2) "
            "in every hour of the season; ERA5/ERA5-Land assign 10 m w.e. to grid boxes with >50% ice cover "
            "(Munoz-Sabater et al. 2021, ESSD 13:4349, section 2.1). "
            "3 perennial_snow: land below the glacier cap whose snow pack never melts out (see preprocess/README.md). "
            "Snow-load variables are NaN wherever surface_type != 1; symbolize classes 2-3 from this flag. "
            f"Cell counts: {n_by_class}."),
    }


def finalize(ds, script):
    """Stamp history; called just before writing."""
    ds.attrs["history"] = (f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} created by preprocess/{script} "
                           "from read-only AZCOT source data")
    return ds


def encoding(ds, chunks=None):
    # CF: coordinate and bounds variables carry no _FillValue.
    enc = {c: {"_FillValue": None} for c in list(ds.coords) + ["climatology_bounds"] if c in ds.variables
           and ds[c].dtype.kind == "f"}
    for v, da in ds.data_vars.items():
        if v != "climatology_bounds" and da.dtype.kind == "f" and da.ndim >= 2:
            e = {"zlib": True, "complevel": 2, "_FillValue": FILL, "dtype": "float32"}
            if chunks and da.ndim > 2:
                e["chunksizes"] = tuple(1 if d not in ("lat", "lon") else da.sizes[d] for d in da.dims)
            enc[v] = e
    return enc
