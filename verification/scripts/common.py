"""Clean-room helpers for re-verifying AZCOT_DATA_ISSUES.md.

Written from scratch for the 2026-10-12 verification; nothing is imported from eda/ or preprocess/.
All AZCOT inputs are opened READ ONLY (netCDF4 mode 'r', PIL for GeoTIFFs, eccodes for GRIB).

Grid convention used everywhere here: the Metrics grid, i.e. latitude ASCENDING 60 -> 90 (121 rows),
longitude -180 -> 179.75 (1440 columns). Raw hourly files store latitude DESCENDING, so every raw field
is flipped after checking its coordinate vectors.
"""
import calendar
import os

import netCDF4
import numpy as np

AZCOT = "/import/beegfs/SNAP/rltorgerson/AZCOT"
RAW = f"{AZCOT}/disk1/data"
MET = f"{AZCOT}/disk1/Metrics"
ATLAS = f"{AZCOT}/disk2/Atlas"
AKCASC = "/import/AKCASC/data/cds/reanalysis-era5-single-levels"
OUT = "/import/beegfs/CMIP6/jdpaul3/azcot_verify"

MONTHS = ["oct", "nov", "dec", "jan", "feb", "mar"]
MONTH_NUM = {"oct": 10, "nov": 11, "dec": 12, "jan": 1, "feb": 2, "mar": 3}
MONTH_DAYS = {"oct": 31, "nov": 30, "dec": 31, "jan": 31, "feb": 29, "mar": 31}
YEARS = list(range(1991, 2021))
WINDOWS = [(0, 5), (6, 11), (12, 17), (18, 23)]

NLAT, NLON = 121, 1440
LAT = 60.0 + 0.25 * np.arange(NLAT)            # ascending, Metrics order
LON = -180.0 + 0.25 * np.arange(NLON)

KN_TO_MPH = 1.150779448   # 1 international knot = 1852 m/h = 1.150779 statute mph
MS_TO_KN = 1.943844492    # 1 m/s = 3600/1852 kn
M_TO_IN = 39.37007874
SWE_M_TO_LBFT2 = 39.37007874 * 5.2   # TR-26-5 eq. 4: SL = SWE[in] x 5.2

RAW_VAR = {"2T": "2T_GDS0_SFC", "SKT": "SKT_GDS0_SFC", "WCT": "WCT", "WS10_knots": "WS10"}


def all_days():
    """The 183 calendar days of the AZCOT season, as (mon, dd) with dd an int."""
    return [(m, d) for m in MONTHS for d in range(1, MONTH_DAYS[m] + 1)]


def years_for_day(mon, dd):
    if mon == "feb" and dd == 29:
        return [y for y in YEARS if calendar.isleap(y)]
    return YEARS


def k_to_f(k):
    return (k - 273.15) * 9.0 / 5.0 + 32.0


def wct_nws(t_f, v_mph):
    """NWS 2001 wind chill (TR-26-5 eq. 3), applied with no validity clipping."""
    v16 = np.power(v_mph, 0.16)
    return 35.74 + 0.6215 * t_f - 35.75 * v16 + 0.4275 * t_f * v16


def raw_path(mon, dd, year, hour, var):
    return f"{RAW}/{mon}/{dd:02d}/{year % 100:02d}{MONTH_NUM[mon]:02d}{dd:02d}{hour:02d}.{var}.nc"


def read_raw(path, varname):
    """Read one raw 0.25 deg hourly field, check its grid, return float64 array in Metrics (ascending) order."""
    with netCDF4.Dataset(path, "r") as ds:
        lat = np.asarray(ds["g0_lat_0"][:])
        lon = np.asarray(ds["g0_lon_1"][:])
        v = ds[varname]
        v.set_auto_mask(False)
        a = np.asarray(v[:], dtype=np.float64)
        fv = getattr(v, "_FillValue", None)
        it = getattr(v, "initial_time", None)
    if not (np.allclose(np.asarray(lat), LAT[::-1]) and np.allclose(np.asarray(lon), LON)):
        raise ValueError(f"unexpected grid in {path}")
    if fv is not None and np.isfinite(fv):
        a[a == fv] = np.nan
    return a[::-1, :], it


def grib_path(mon, dd, year, hour, var):
    return raw_path(mon, dd, year, hour, var)[:-3] + ".grib"


def read_grib(path, short_name, year, mon, dd, hour):
    """Read a one-message raw GRIB file; check parameter, date/time and grid. Returns Metrics-order float64 array."""
    import eccodes
    with open(path, "rb") as fh:
        g = eccodes.codes_grib_new_from_file(fh)
        try:
            k = {n: eccodes.codes_get(g, n) for n in
                 ("shortName", "dataDate", "dataTime", "Ni", "Nj", "latitudeOfFirstGridPointInDegrees",
                  "longitudeOfFirstGridPointInDegrees", "jScansPositively", "bitmapPresent")}
            vals = eccodes.codes_get_values(g).astype(np.float64)
        finally:
            eccodes.codes_release(g)
        if eccodes.codes_grib_new_from_file(fh) is not None:
            raise ValueError(f"more than one message in {path}")
    want_date = year * 10000 + MONTH_NUM[mon] * 100 + dd
    if (k["shortName"] != short_name or k["dataDate"] != want_date or k["dataTime"] != hour * 100
            or k["Ni"] != NLON or k["Nj"] != NLAT or k["latitudeOfFirstGridPointInDegrees"] != 90.0
            or k["longitudeOfFirstGridPointInDegrees"] != -180.0 or k["jScansPositively"] != 0):
        raise ValueError(f"unexpected GRIB header in {path}: {k}")
    if k["bitmapPresent"]:
        vals[vals == 9999] = np.nan
    return vals.reshape(NLAT, NLON)[::-1, :]


def read_metrics(path, names):
    """Read Metrics variables (already ascending latitude); check grid."""
    out = {}
    with netCDF4.Dataset(path, "r") as ds:
        lat = np.asarray(ds["g0_lat_0"][:])
        lon = np.asarray(ds["g0_lon_1"][:])
        if not (np.allclose(lat, LAT) and np.allclose(lon, LON)):
            raise ValueError(f"unexpected grid in {path}")
        for n in names:
            v = ds[n]
            v.set_auto_mask(False)
            out[n] = np.asarray(v[:], dtype=np.float64)
    return out


def metrics_vars(path):
    with netCDF4.Dataset(path, "r") as ds:
        return list(ds.variables)


def read_atlas_tif(path):
    """Atlas GeoTIFF -> (121, 1440) float64 in Metrics order; NaN outside the Atlas land mask.

    Checks the .tfw world file: 0.25 deg pixels, upper-left pixel centre (-180, 90), 1441 columns (wrap column dropped).
    """
    from PIL import Image
    with open(path[:-4] + ".tfw") as f:
        tfw = [float(x) for x in f.read().split()]
    if not (np.allclose(tfw[0], 0.25) and np.allclose(tfw[3], -0.25)
            and np.allclose(tfw[4], -180.0) and np.allclose(tfw[5], 90.0)):
        raise ValueError(f"unexpected world file for {path}: {tfw}")
    with Image.open(path) as im:
        a = np.asarray(im, dtype=np.float64)
    if a.shape != (121, 1441):
        raise ValueError(f"unexpected TIF shape {a.shape} for {path}")
    a = a[:, :1440]
    a[a < -1e30] = np.nan
    return a[::-1, :]


def cell(lat, lon):
    """Indices (i, j) of a cell on the Metrics grid."""
    i = int(round((lat - 60.0) / 0.25))
    j = int(round((lon + 180.0) / 0.25))
    return i, j


SITES = {
    "Fairbanks": (64.75, -147.75),
    "Utqiagvik": (71.25, -156.75),
    "Eureka": (80.0, -86.0),
    "Oymyakon": (63.5, 142.75),
}


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p
