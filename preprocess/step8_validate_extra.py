"""Step 8: validate the t2 / wspd / sd coverages (steps 6-7) against Metrics and the Atlas.

Writes validation/validation_report_extra.md; exits non-zero if a check fails.
Unit conversions applied to Metrics before comparing: 2T K -> degF; WSPD m/s -> knots; SD m -> inches.
"""
import datetime as dt
import os
import sys
from multiprocessing import Pool

import numpy as np
import xarray as xr
from PIL import Image

from config import ATLAS, COVERAGES, DAYS, INTERMEDIATE, MONTH_NUM, MONTHS, metrics_daily, out_path

TOL = {"t2": 0.01, "wspd": 0.01, "sd": 0.01}
K2F = lambda k: (k - 273.15) * 9 / 5 + 32


def day_checks(args):
    m, d = args
    out = {}
    t = xr.open_dataset(INTERMEDIATE / "hourly_reduce" / "t2" / f"{m}_{d:02d}.nc")
    w = xr.open_dataset(INTERMEDIATE / "hourly_reduce" / "wspd" / f"{m}_{d:02d}.nc")
    s = xr.open_dataset(INTERMEDIATE / "hourly_reduce" / "sd" / f"{m}_{d:02d}.nc")
    with xr.open_dataset(metrics_daily("2T", m, d)) as mt:
        out["t2 mean vs Metrics averageTemp (K->F)"] = np.nanmax(abs(t["mean"].values - K2F(mt.averageTemp.values)))
        out["t2 mean_annual_min vs Metrics min_2T (K->F)"] = np.nanmax(abs(t["mean_annual_min"].values
                                                                          - K2F(mt.min_2T.values)))
        out["t2 min <= Metrics percentile_1 (violations)"] = float(np.sum(t["min"].values > K2F(mt.percentile_1.values) + 0.01))
    with xr.open_dataset(metrics_daily("WSPD", m, d)) as mw:
        out["wspd mean vs Metrics averageWSPD (m/s->kn)"] = np.nanmax(abs(w["mean"].values
                                                                         - mw.averageWSPD.values * 1.943844))
    with xr.open_dataset(metrics_daily("SD", m, d)) as ms:
        sd_m = ms[list(ms.data_vars)[0]].values  # SD mean, misnamed averageSL in Metrics
        missing = s.attrs.get("n_missing_hours", 0)
        key = "sd mean vs Metrics SD mean (m->in, relative; days with missing hours skipped)"
        if missing == 0:
            theirs = sd_m * 39.3701
            out[key] = np.nanmax(abs(s["mean"].values - theirs) / np.maximum(abs(theirs), 1.0))
            out["sd max vs Metrics max_SD (m->in)"] = np.nanmax(abs(s["max"].values - ms.max_SD.values * 39.3701))
        else:
            out[key] = 0.0
            out["sd max vs Metrics max_SD (m->in)"] = 0.0
            out["sd days with missing (all-NaN) hours"] = 1.0
    tif = ATLAS / m / "Daily" / f"{d:02d}" / "2T" / "Extreme" / f"{m}_{d:02d}_2T_min.tif"
    if tif.exists():
        a = np.array(Image.open(tif), dtype=np.float64)
        a[a < -1e30] = np.nan
        a = a[::-1, :1440]
        k = np.isfinite(a)
        diff = a[k] - t["min"].values[k]
        out["t2: Atlas 2T 'lowest recorded' colder than our true min (cells, violations)"] = float(np.sum(diff < -0.01))
        out["t2: share of cells where Atlas 2T min equals ours (info, lowest day)"] = -float(np.mean(abs(diff) <= 0.01))
    for f in (t, w, s):
        f.close()
    return out


def hist_checks():
    out = {}
    for var in ("t2", "wspd", "sd"):
        with xr.open_dataset(COVERAGES / f"azcot_{var}_histogram_monthly.nc") as h:
            c = h[f"{var}_hour_counts"]
            tot = c.sum("bin").values
            n = h["n_hours"].values[:, None, None]
            has = tot > 0
            out[f"{var} histogram totals == n_hours (cells with data, violations)"] = float(
                np.sum(has & (tot != np.broadcast_to(n, tot.shape))))
    # SD frequency >= 8, 15, 20, 40 in vs Metrics (monthly mean of daily Metrics frequencies)
    with xr.open_dataset(COVERAGES / "azcot_sd_histogram_monthly.nc") as h:
        for mon_i, mon in enumerate(MONTHS):
            days = [d for m, d in DAYS if m == mon]
            for thr in (8, 15, 20, 40):
                ours = (h.sd_hour_counts.isel(time=mon_i).sel(bin=slice(thr + 1, None)).sum("bin")
                        / h.n_hours.isel(time=mon_i)).values * 100
                # Metrics divides by 720 even when hours are missing (they count as "not exceeding"), so rebuild
                # its hour counts (frequency x 7.2) and divide by the hours that exist.
                hours = np.zeros(h.sd_hour_counts.shape[-2:])
                for d in days:
                    with xr.open_dataset(metrics_daily("SD", mon, d)) as ms:
                        hours += ms[f"frequency_{thr}"].values * 7.2
                theirs = hours / float(h.n_hours.isel(time=mon_i)) * 100
                k = np.isfinite(theirs) & (h.sd_hour_counts.isel(time=mon_i).sum("bin").values > 0)
                key = f"sd % hours >= {thr} in vs Metrics frequency_{thr} (monthly, %-points)"
                out[key] = max(out.get(key, 0), float(np.max(abs(ours[k] - theirs[k]))))
    return out


def main():
    with Pool(int(os.environ.get("SLURM_CPUS_PER_TASK", 8))) as pool:
        per_day = pool.map(day_checks, DAYS)
    keys = sorted({k for r in per_day for k in r})
    checks = {k: max(r.get(k, 0) for r in per_day) for k in keys}
    checks["sd days with missing (all-NaN) hours"] = sum(r.get("sd days with missing (all-NaN) hours", 0)
                                                        for r in per_day)
    info = "t2: share of cells where Atlas 2T min equals ours (info, lowest day)"
    checks[info] = -max(r.get(info, 0) for r in per_day)  # stored negated so max() picked the lowest share
    checks.update(hist_checks())

    def passed(k, v):
        if "violations" in k:
            return v == 0
        if "(info" in k or k == "sd days with missing (all-NaN) hours":
            return True  # informational
        if "relative" in k:
            return v <= 5e-5
        if "%-points" in k:
            return v <= 0.2  # small slack for values exactly on a threshold
        return v <= 0.01

    ok = all(passed(k, v) for k, v in checks.items())
    md = [f"# AZCOT preprocess validation: t2 / wspd / sd ({dt.datetime.now():%Y-%m-%d %H:%M})", "",
          "| check | max diff | pass |", "|---|---:|---|"]
    md += [f"| {k} | {v:.4g} | {'yes' if passed(k, v) else 'NO'} |" for k, v in checks.items()]
    md += ["", f"**Overall: {'PASS' if ok else 'FAIL'}**"]
    text = "\n".join(md)
    out_path("validation", "validation_report_extra.md").write_text(text + "\n")
    print(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
