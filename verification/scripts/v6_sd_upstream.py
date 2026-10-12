"""V6: (a) issue 6 monthly bias of Metrics SD frequency_8 on land; (b) issue 5 upstream check: the independent AKCASC
ERA5-Land copy (daily 12 UTC sde) has real values on month-end days whose AZCOT 12 UTC file is all-NaN, and matches
AZCOT exactly on normal days (so it is the same product). Prints a summary; writes tables/v6_sd_upstream.csv."""
import glob
import os

import netCDF4
import numpy as np
import pandas as pd

from common import MONTHS, OUT, raw_path

HERE = os.path.dirname(os.path.abspath(__file__))
z = np.load(f"{OUT}/misc/v5_sd_monthly.npz")
land = z["land"]
print("issue 6: land-mean monthly frequency_8 (% of hours >= 8 in), Metrics vs divided by valid hours")
for m in MONTHS:
    a, b = z[f"{m}_met"][land].mean(), z[f"{m}_fix"][land].mean()
    print(f"  {m}: Metrics {a:6.2f}  corrected {b:6.2f}  diff {b - a:5.2f} pp  (relative {100 * (b - a) / b:4.1f}%)")

AK = "/import/AKCASC/data/cds/reanalysis-era5-land/sd"
rows = []
for f in sorted(glob.glob(f"{AK}/*.nc")):
    with netCDF4.Dataset(f) as ds:
        t = netCDF4.num2date(ds["time"][:], ds["time"].units)
        lat = np.asarray(ds["latitude"][:])
        lon = np.asarray(ds["longitude"][:])
        sel = np.where(lat >= 59.95)[0]
        for k, x in enumerate(t):
            if not (1991 <= x.year <= 2020):
                continue
            mon = {10: "oct", 11: "nov", 12: "dec", 1: "jan", 2: "feb", 3: "mar"}.get(x.month)
            if mon is None or x.day not in (14, 28, 29, 30, 31):
                continue
            p = raw_path(mon, x.day, x.year, 12, "SD")
            if not os.path.exists(p):
                continue
            a = np.asarray(ds["sde"][k, sel, :].filled(np.nan) if np.ma.isMaskedArray(ds["sde"][k, sel, :]) else ds["sde"][k, sel, :], np.float64)
            with netCDF4.Dataset(p) as r:
                b = np.asarray(r["sde"][:].filled(np.nan), np.float64)
                rlat, rlon = np.asarray(r["latitude"][:]), np.asarray(r["longitude"][:])
            # align AKCASC to the AZCOT grid (both 0.1 deg, lat descending); match longitude ordering
            alat = lat[sel]
            assert np.allclose(alat, rlat, atol=1e-3), (alat[:3], rlat[:3])
            if not np.allclose(lon, rlon, atol=1e-3):
                order = np.argsort(np.where(lon >= 180, lon - 360, lon))
                a = a[:, order]
                assert np.allclose(np.where(lon >= 180, lon - 360, lon)[order], rlon, atol=1e-3)
            okb = np.isfinite(b)
            oka = np.isfinite(a)
            both = oka & okb
            rows.append(dict(date=f"{x.year}-{x.month:02d}-{x.day:02d}", azcot_nonnan=int(okb.sum()), akcasc_nonnan=int(oka.sum()),
                             maxabs_both=float(np.abs(a[both] - b[both]).max()) if both.any() else np.nan))
df = pd.DataFrame(rows)
df.to_csv(os.path.join(HERE, "..", "tables", "v6_sd_upstream.csv"), index=False)
miss = df[df.azcot_nonnan == 0]
okd = df[df.azcot_nonnan > 0]
print(f"issue 5 upstream: {len(df)} dates compared at 12 UTC")
print(f"  AZCOT all-NaN dates: {len(miss)}; AKCASC non-NaN cells on those dates: min {miss.akcasc_nonnan.min()} max {miss.akcasc_nonnan.max()}")
print(f"  dates with AZCOT data: {len(okd)}; max |AKCASC - AZCOT| over shared cells: {okd.maxabs_both.max():.3g} m; "
      f"AZCOT cells {okd.azcot_nonnan.unique()[:3]} AKCASC cells {okd.akcasc_nonnan.unique()[:3]}")
