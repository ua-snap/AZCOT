"""Shared configuration for the AZCOT preprocessing pipeline.

Source data is read-only. Every writer in this pipeline goes through `out_path()`, which refuses to
write anywhere under SOURCE_ROOT.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

SOURCE_ROOT = Path("/import/beegfs/SNAP/rltorgerson/AZCOT")
RAW = SOURCE_ROOT / "disk1" / "data"
METRICS = SOURCE_ROOT / "disk1" / "Metrics"
ATLAS = SOURCE_ROOT / "disk2" / "Atlas"

OUT_ROOT = Path(os.environ.get("AZCOT_PRE_OUT", "/import/beegfs/CMIP6/jdpaul3/azcot_preprocess"))
INTERMEDIATE = OUT_ROOT / "intermediate"
COVERAGES = OUT_ROOT / "coverages"
VALIDATION = OUT_ROOT / "validation"
LOGS = OUT_ROOT / "logs"

# Cold-season calendar WITHOUT Feb 29 (Feb 29 has only 8 leap years and a buggy min_WCT in Metrics).
MONTHS = ["oct", "nov", "dec", "jan", "feb", "mar"]
MONTH_NUM = {"oct": 10, "nov": 11, "dec": 12, "jan": 1, "feb": 2, "mar": 3}
DAYS_IN = {"oct": 31, "nov": 30, "dec": 31, "jan": 31, "feb": 28, "mar": 31}
DAYS = [(m, d) for m in MONTHS for d in range(1, DAYS_IN[m] + 1)]  # 182 calendar days
YEARS = list(range(1991, 2021))  # 30 years; every calendar day pools all 30 (720 hours)
HOURS = list(range(24))

# Nominal (non-leap) season used only to give each climatological day a date stamp.
NOMINAL_DATES = pd.to_datetime([f"{2001 if MONTH_NUM[m] >= 10 else 2002}-{MONTH_NUM[m]:02d}-{d:02d}" for m, d in DAYS])
NOMINAL_MONTHS = pd.to_datetime([f"{2001 if MONTH_NUM[m] >= 10 else 2002}-{MONTH_NUM[m]:02d}-15" for m in MONTHS])

# Snow load: TR-26-5 eq. 4, SL[lb/ft2] = SWE[in] * 5.2. Verified to reproduce Metrics averageSL/max_SL.
SWE_M_TO_SL = 1000.0 / 25.4 * 5.2  # 204.724 lb/ft2 per m w.e.
ERA5_GLACIER_SWE_M = 10.0  # ERA5/ERA5-Land constant snow mass on glacier points (Munoz-Sabater et al. 2021, s2.1)
GLACIER_SL = ERA5_GLACIER_SWE_M * SWE_M_TO_SL  # 2047.24 lb/ft2

# Grid (output convention: lat ascending like the Metrics files; lon -180..179.75).
LAT = np.round(np.arange(60.0, 90.0001, 0.25), 2)
LON = np.round(np.arange(-180.0, 180.0, 0.25), 2)

SURFACE_TYPES = {0: "ocean", 1: "land", 2: "glacier", 3: "perennial_snow"}

GLOBAL_ATTRS = {
    "title": "AZCOT curated cold-season climatology coverages",
    "source": "ERA5 hourly reanalysis via the AZCOT dataset (ERDC/CRREL), /beegfs/SNAP/rltorgerson/AZCOT",
    "climatology_period": "1991-2020, October-March, Feb 29 excluded",
    "references": ("ERDC/CRREL TR-26-5 (2026); ERDC/CRREL SR-25-2 (2025); Munoz-Sabater et al. (2021), ERA5-Land, "
                   "ESSD 13:4349-4383, doi:10.5194/essd-13-4349-2021"),
    "institution": "SNAP, University of Alaska Fairbanks",
    "Conventions": "CF-1.8",
    "history": "",
    "code": "AZCOT repo, preprocess/",
}


def out_path(*parts):
    """Return a path under OUT_ROOT (creating its parent), refusing anything inside the source tree."""
    p = OUT_ROOT.joinpath(*parts).resolve()
    src = SOURCE_ROOT.resolve()
    if p == src or src in p.parents or Path("/beegfs/SNAP/rltorgerson") in p.parents:
        raise RuntimeError(f"refusing to write inside the read-only source tree: {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def raw_files(var, month, day):
    """Hourly source files for one calendar day: {(year, hour): path}. var is 'WCT' or 'SWE'."""
    ext = "nc" if var == "WCT" else "grib"
    folder = RAW / month / f"{day:02d}"
    out = {}
    for f in folder.glob(f"??{MONTH_NUM[month]:02d}{day:02d}??.{var}.{ext}"):
        yy, hh = int(f.name[0:2]), int(f.name[6:8])
        out[(1900 + yy if yy >= 50 else 2000 + yy, hh)] = f
    return out


def metrics_daily(var, month, day):
    return METRICS / f"daily_{var}_stats" / f"{month}_{day:02d}_{var}_stats.nc"
