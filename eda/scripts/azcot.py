"""Shared helpers for the AZCOT Metrics EDA.

The source dataset is read-only; nothing here writes outside eda/.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

METRICS = Path("/import/beegfs/SNAP/rltorgerson/AZCOT/disk1/Metrics")
EDA = Path(__file__).resolve().parents[1]
CACHE = EDA / "cache"
FIGS = EDA / "figures"

# Cold season, Oct 1 - Mar 31, including Feb 29 (183 daily files per variable).
MONTHS = ["oct", "nov", "dec", "jan", "feb", "mar"]
DAYS_IN = {"oct": 31, "nov": 30, "dec": 31, "jan": 31, "feb": 29, "mar": 31}
DAYS = [(m, d) for m in MONTHS for d in range(1, DAYS_IN[m] + 1)]
# Reference (leap) season used only to give each day a date for plotting.
DATES = pd.date_range("2019-10-01", "2020-03-31", freq="D")
assert len(DATES) == len(DAYS)

SL_GLACIER_CAP = 2047.248  # lb/ft2 == ~10 m w.e., ERA5 snow cap over permanent ice

# Representative land points (name, lat, lon).
LOCATIONS = [
    ("Fairbanks, AK", 64.84, -147.72),
    ("Utqiagvik, AK", 71.29, -156.79),
    ("Yellowknife, NT", 62.45, -114.37),
    ("Eureka, NU", 79.99, -85.93),
    ("Pituffik, GL", 76.53, -68.70),
    ("Tromsø, NO", 69.65, 18.96),
    ("Norilsk, RU", 69.35, 88.20),
    ("Oymyakon, RU", 63.46, 142.79),
]


def daily_path(var, month, day):
    return METRICS / f"daily_{var}_stats" / f"{month}_{day:02d}_{var}_stats.nc"


def open_daily(var, month, day):
    return xr.open_dataset(daily_path(var, month, day))


def load_cube(name):
    """Open a cached (day, lat, lon) cube built by build_cubes.py."""
    ds = xr.open_dataset(CACHE / f"{name}_daily.nc")
    return ds.assign_coords(date=("day", DATES))


def load_masks():
    return xr.open_dataset(CACHE / "masks.nc")


def nearest_land_cell(lat, lon, land, max_km=60):
    """Return (ilat, ilon) of the land cell nearest to (lat, lon) on the 0.25° grid."""
    lats, lons = land.g0_lat_0.values, land.g0_lon_1.values
    la2, lo2 = np.meshgrid(lats, lons, indexing="ij")
    dlon = np.radians(((lo2 - lon + 180) % 360) - 180)
    km = 6371 * np.arccos(np.clip(np.sin(np.radians(lat)) * np.sin(np.radians(la2))
                                  + np.cos(np.radians(lat)) * np.cos(np.radians(la2)) * np.cos(dlon), -1, 1))
    km = np.where(land.values, km, np.inf)
    i, j = np.unravel_index(np.argmin(km), km.shape)
    if km[i, j] > max_km:
        raise ValueError(f"no land cell within {max_km} km of {lat},{lon}")
    return i, j
