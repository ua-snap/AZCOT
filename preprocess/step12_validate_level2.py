"""Step 12: validate the Level 2 coverages (frostbite, steps 9 + 11; snowfall loads, steps 10 + 11).

Writes validation/validation_report_level2.md; exits non-zero if a check fails.
Independent re-computations use their own reading and arithmetic (not the step 9/10 functions):
  * frostbite: class counts for a few cells and days straight from the raw 2T and WS10 files;
  * snowfall: 24-hour maxima (pandas rolling sums) and storm totals (a plain loop) for a few cells and one winter,
    straight from the SNAP ERA5 snowfall files.
"""
import datetime as dt
import sys

import numpy as np
import pandas as pd
import xarray as xr

from config import COVERAGES, DAYS, INTERMEDIATE, MONTH_NUM, MONTHS, RAW, SWE_M_TO_SL, out_path
from step10_reduce_snowfall import GAP_H, SF_DIR, WET_MM_H

CELLS = {"Fairbanks": (64.75, -147.75), "Utqiagvik": (71.25, -156.75), "Tromso": (69.75, 19.0),
         "Valdez": (61.0, -146.25), "Oymyakon": (63.5, 142.75)}
FB_DAYS = [("nov", 1), ("jan", 15), ("mar", 31)]
SF_WINTER = 2000  # Oct 2000 - Mar 2001


def fb_point_checks():
    """Max |difference| in class counts (hours), recomputed from raw files at CELLS x FB_DAYS."""
    worst = 0
    for m, d in FB_DAYS:
        with xr.open_dataset(INTERMEDIATE / "frostbite" / f"{m}_{d:02d}.nc") as ds:
            edges = ds["bin"].values
            ours = {k: ds["counts"].sel(lat=la, lon=lo).values for k, (la, lo) in CELLS.items()}
        mine = {k: np.zeros(4, int) for k in CELLS}
        for f in sorted((RAW / m / f"{d:02d}").glob(f"??{MONTH_NUM[m]:02d}{d:02d}??.2T.nc")):
            stem = str(f)[: -len(".2T.nc")]
            with xr.open_dataset(f) as a, xr.open_dataset(stem + ".WS10_knots.nc") as w:
                for k, (la, lo) in CELLS.items():
                    tc = float(a["2T_GDS0_SFC"].sel(g0_lat_0=la, g0_lon_1=lo, method="nearest")) - 273.15
                    mph = float(w["WS10"].sel(g0_lat_0=la, g0_lon_1=lo, method="nearest")) * 1852 / 1609.344
                    if -4.8 - tc <= 0:
                        c = 0
                    else:
                        ft = max(0.0, 2111 - 24.5 * (0.667 * mph * 1.6 + 4.8)) * (-4.8 - tc) ** -1.668
                        c = 3 if ft <= 5 else 2 if ft <= 45 else 1 if ft <= 120 else 0
                    mine[k][c] += 1
        for k in CELLS:
            o = ours[k]
            cls = np.array([o[edges >= 9999].sum(), o[(edges > 45) & (edges <= 120)].sum(),
                            o[(edges > 5) & (edges <= 45)].sum(), o[edges <= 5].sum()])
            worst = max(worst, int(abs(cls - mine[k]).max()))
    return worst


def fb_checks():
    out = {"frostbite: class counts vs independent raw recomputation (5 cells x 3 days, hours)": fb_point_checks()}
    h = xr.open_dataset(COVERAGES / "azcot_frostbite_histogram_monthly.nc")
    c = h["frostbite_hour_counts"]
    tot = c.sum("bin")
    out["frostbite histogram totals == n_hours (cells, violations)"] = int((tot != h["n_hours"]).sum())
    defined = c.sel(bin=slice(None, 9999)).sum("bin")
    t2 = xr.open_dataset(COVERAGES / "azcot_t2_histogram_monthly.nc")["t2_hour_counts"]
    le23, le24 = t2.sel(bin=slice(None, 23)).sum("bin"), t2.sel(bin=slice(None, 24)).sum("bin")
    # Eq. 5 is defined iff 2T < 23.36 degF, so defined hours lie between the hours <= 23 and <= 24 degF.
    out["frostbite defined hours within t2 hours <= 23 / <= 24 degF (cell-months, violations)"] = int(
        ((defined.values < le23.values) | (defined.values > le24.values)).sum())
    for res in ("daily", "monthly", "seasonal"):
        ds = xr.open_dataset(COVERAGES / f"azcot_frostbite_{res}.nc")
        s = sum(ds[f"frostbite_{k}_share"] for k in ("red", "amber", "green", "none"))
        out[f"frostbite {res}: shares sum to 100 (max |error|, %)"] = float(abs(s - 100).max())
        fmin = ds["frostbite_time_min"]
        out[f"frostbite {res}: frostbite_time_min < 0 (cells, violations)"] = int((fmin < 0).sum())
    # info: exact red share vs the old wind-chill approximation, land mean (seasonal)
    se = xr.open_dataset(COVERAGES / "azcot_frostbite_seasonal.nc")
    ws = xr.open_dataset(COVERAGES / "azcot_wct_stats_seasonal.nc")
    land = se["surface_type"] == 1
    out["(info) land-mean seasonal red share, exact (%)"] = float(se["frostbite_red_share"].where(land).mean())
    out["(info) land-mean seasonal share WCT <= -60 F, old approximation (%)"] = float(
        ws["wct_frequency"].sel(wct_threshold=-60).where(land).mean())
    return out


def sf_series(la, lo):
    """Hourly snowfall (m w.e.) at one cell, Sep 1 of SF_WINTER to Apr 30 of the next year, read independently."""
    parts = []
    for y, m in [(SF_WINTER, m) for m in (9, 10, 11, 12)] + [(SF_WINTER + 1, m) for m in (1, 2, 3, 4)]:
        with xr.open_dataset(f"{SF_DIR}/reanalysis-era5-single-levels_sf_{y}_{m:02d}.nc") as ds:
            parts.append(ds["sf"].sel(latitude=la, longitude=lo % 360).to_series())
    return pd.concat(parts).clip(lower=0)


def storms_loop(sf):
    """Storm totals keyed by end time (plain loop; same definition as step 10)."""
    wet = sf.values >= WET_MM_H / 1000
    out, i, n = {}, 0, len(sf)
    while i < n:
        if not wet[i]:
            i += 1
            continue
        start = last = i
        j = i + 1
        while j < n and j - last - 1 <= GAP_H:
            if wet[j]:
                last = j
            j += 1
        out[sf.index[last]] = (sf.values[start:last + 1].sum(), last - start + 1)
        i = last + 1
    return out


def sf_checks():
    out = {}
    w = xr.open_dataset(INTERMEDIATE / "snowfall" / f"winter_{SF_WINTER}.nc")
    worst24, worst_storm = 0.0, 0.0
    for k, (la, lo) in CELLS.items():
        sf = sf_series(la, lo)
        r24 = sf.rolling(24).sum() * SWE_M_TO_SL
        daymax = r24.groupby(r24.index.floor("D")).max()
        r72 = sf.rolling(72).sum() * SWE_M_TO_SL
        daymax72 = r72.groupby(r72.index.floor("D")).max()
        storms = storms_loop(sf)
        smax = pd.Series(0.0, index=daymax.index)
        last_kept = pd.Timestamp(w["date"].values[-1]) + pd.Timedelta(hours=23)
        for end, (tot, hours) in storms.items():
            start = end - pd.Timedelta(hours=hours - 1)
            if start <= last_kept < end:  # storm running across the season end -> credited to the last kept day
                end = last_kept
            day = end.floor("D")
            smax[day] = max(smax[day], tot * SWE_M_TO_SL)
        ours = w.sel(lat=la, lon=lo)
        dates = pd.DatetimeIndex(ours["date"].values)
        worst24 = max(worst24, float(np.max(abs(ours["sf24_daymax"].values - daymax.reindex(dates).values))),
                      float(np.max(abs(ours["sf72_daymax"].values - daymax72.reindex(dates).values))))
        worst_storm = max(worst_storm, float(np.max(abs(ours["storm_max"].values - smax.reindex(dates).values))))
    out[f"snowfall: daily max 24-h and 72-h loads vs pandas rolling sums (5 cells, winter {SF_WINTER}, lb/ft2)"] = worst24
    out[f"snowfall: daily max storm total vs plain-loop storms (5 cells, winter {SF_WINTER}, lb/ft2)"] = worst_storm
    for res in ("daily", "monthly", "seasonal"):
        ds = xr.open_dataset(COVERAGES / f"azcot_snowfall_{res}.nc")
        bad = 0
        for v in ("sf24", "storm", "sf72"):
            bad += int((ds[f"{v}_max"] < ds[f"{v}_mean_annual_max"] - 1e-4).sum())
            bad += int((ds[f"{v}_mean_annual_max"] < 0).sum())
        out[f"snowfall {res}: max >= mean annual max >= 0 (cells, violations)"] = bad
    h = xr.open_dataset(COVERAGES / "azcot_snowfall_histogram_monthly.nc")
    out["snowfall histogram day totals == n_days (cells, violations)"] = int(
        (h["sf24_day_counts"].sum("sf24_bin") != h["n_days"]).sum())
    mo = xr.open_dataset(COVERAGES / "azcot_snowfall_monthly.nc")
    from_hist = h["sf24_day_counts"].sel(sf24_bin=slice(10.25, None)).sum("sf24_bin") / 30
    out["snowfall: sf24_ge10_days vs histogram days > 10 (max |diff|, days/yr)"] = float(
        abs(from_hist.values - mo["sf24_ge10_days"].values).max())
    se = xr.open_dataset(COVERAGES / "azcot_snowfall_seasonal.nc")
    land = se["surface_type"] == 1
    out["(info) land-mean record 24-h snowfall load (lb/ft2)"] = float(se["sf24_max"].where(land).mean())
    out["(info) land share with a 24-h load >= 10 lb/ft2 in 30 years (%)"] = float(
        (se["sf24_max"].where(land) >= 10).sum() / land.sum() * 100)
    out["(info) land-mean record storm total (lb/ft2)"] = float(se["storm_max"].where(land).mean())
    out["(info) land share with a storm total >= 20 lb/ft2 in 30 years (%)"] = float(
        (se["storm_max"].where(land) >= 20).sum() / land.sum() * 100)
    return out


def passed(k, v):
    if k.startswith("(info)"):
        return True
    if "violations" in k or "(hours)" in k or "hours)" in k:
        return v == 0
    if "lb/ft2" in k:
        return v <= 1e-3
    return v <= 0.01


def main():
    checks = {}
    checks.update(fb_checks())
    checks.update(sf_checks())
    ok = all(passed(k, v) for k, v in checks.items())
    md = [f"# AZCOT preprocess validation: Level 2 (frostbite, snowfall loads) ({dt.datetime.now():%Y-%m-%d %H:%M})",
          "", f"Storm definition: wet hour >= {WET_MM_H} mm w.e., dry gaps <= {GAP_H} h.", "",
          "| check | value | pass |", "|---|---:|---|"]
    md += [f"| {k} | {v:.4g} | {'yes' if passed(k, v) else 'NO'} |" for k, v in checks.items()]
    md += ["", f"**Overall: {'PASS' if ok else 'FAIL'}**"]
    text = "\n".join(md)
    out_path("validation", "validation_report_level2.md").write_text(text + "\n")
    print(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
