"""Step 5: validate the coverages against the source products and confirm the source data is untouched.

Writes validation/validation_report.md (and prints it). Exits non-zero if a check fails.
"""
import datetime as dt
import os
import random
import sys
from multiprocessing import Pool

import numpy as np
import xarray as xr
from PIL import Image

from config import ATLAS, COVERAGES, DAYS, INTERMEDIATE, METRICS, RAW, SOURCE_ROOT, metrics_daily, out_path

TOL = 0.01  # degF or lb/ft2; float32 storage round-off is ~1e-4
REL_TOL = 5e-5  # Metrics were accumulated in float32: ~1e-5 relative error near the 2047 lb/ft2 glacier cap


def compare_day(args):
    m, d = args
    out = {}
    w = xr.open_dataset(INTERMEDIATE / "hourly_reduce" / "wct" / f"{m}_{d:02d}.nc")
    s = xr.open_dataset(INTERMEDIATE / "hourly_reduce" / "sl" / f"{m}_{d:02d}.nc")
    with xr.open_dataset(metrics_daily("WCT", m, d)) as mw, xr.open_dataset(metrics_daily("SL", m, d)) as ms:
        out["wct mean vs Metrics averageTemp"] = np.nanmax(abs(w["mean"].values - mw["averageTemp"].values))
        out["wct mean_annual_min vs Metrics min_WCT"] = np.nanmax(abs(w["mean_annual_min"].values - mw["min_WCT"].values))
        out["wct min <= Metrics percentile_1 (violations)"] = float(np.sum(w["min"].values > mw["percentile_1"].values + TOL))
        for name, ours, theirs in (("sl mean vs Metrics averageSL", s["mean"].values, ms["averageSL"].values),
                                   ("sl max vs Metrics max_SL", s["max"].values, ms["max_SL"].values)):
            out[name] = np.nanmax(abs(ours - theirs))
            out[name + " (relative)"] = np.nanmax(abs(ours - theirs) / np.maximum(abs(theirs), 1.0))
    tif = ATLAS / m / "Daily" / f"{d:02d}" / "WCT" / "Extreme" / f"{m}_{d:02d}_WCT_min.tif"
    a = np.array(Image.open(tif), dtype=np.float64)
    a[a < -1e30] = np.nan
    a = a[::-1, :1440]
    k = np.isfinite(a)
    out["wct min vs Atlas Extreme TIFF (land cells)"] = np.max(abs(w["min"].values[k] - a[k]))
    w.close()
    s.close()
    return out


def source_untouched(started):
    """Check permissions and modification times of the source files this pipeline reads."""
    lines = []
    data_dirs = [SOURCE_ROOT / "disk1", SOURCE_ROOT / "disk2", RAW, METRICS, ATLAS, RAW / "jan" / "15",
                 METRICS / "daily_WCT_stats", METRICS / "daily_SL_stats"]
    writable = [str(p) for p in data_dirs if os.access(p, os.W_OK)]
    lines.append(f"- write permission for {os.environ.get('USER')} on data directories (disk1, disk2 and below): "
                 f"{'NONE' if not writable else writable}")
    if os.access(SOURCE_ROOT, os.W_OK):
        lines.append(f"- WARNING: the top-level {SOURCE_ROOT} directory is group-writable (snap), so entries directly "
                     "inside it could be renamed or removed. This pipeline never writes there (config.out_path guard); "
                     "the owner may want `chmod g-w` on it.")
    used = [metrics_daily(v, m, d) for v in ("WCT", "SL") for m, d in DAYS] + [metrics_daily("SD", "jan", 15)]
    rng = random.Random(0)
    raw_sample = [RAW / m / f"{d:02d}" for m, d in rng.sample(DAYS, 20)]
    for folder in raw_sample:
        used += rng.sample(sorted(folder.glob("*.WCT.nc")), 50) + rng.sample(sorted(folder.glob("*.SWE.grib")), 50)
    newer = [p for p in used if p.stat().st_mtime >= started]
    lines.append(f"- {len(used)} source files checked (all Metrics files used + 2,000 random raw files): "
                 f"{len(newer)} modified since the pipeline started")
    return lines, not writable and not newer


def main():
    first = min((p.stat().st_mtime for p in (INTERMEDIATE / "hourly_reduce").rglob("*.nc")), default=None)
    with Pool(int(os.environ.get("SLURM_CPUS_PER_TASK", 8))) as pool:
        per_day = pool.map(compare_day, DAYS)
    checks = {k: max(r[k] for r in per_day) for k in per_day[0]}
    def passed(k, v):
        if "violations" in k:
            return v == 0
        if k.endswith("(relative)"):
            return v <= REL_TOL
        return v <= TOL or checks.get(k + " (relative)", np.inf) <= REL_TOL

    ok = all(passed(k, v) for k, v in checks.items())

    seas_w = xr.open_dataset(COVERAGES / "azcot_wct_climatology_seasonal.nc")
    seas_s = xr.open_dataset(COVERAGES / "azcot_sl_climatology_seasonal.nc")
    st = seas_w["surface_type"]
    with xr.open_dataset(INTERMEDIATE / "surface_type.nc") as stf:
        e5l = stf["era5land_mask"] == 1  # the report's land definition (ERA5-Land), incl. ice sheets for WCT
    report = {
        "Average Oct-Mar WCT over land (degF)": (float(seas_w.wct_mean.where(e5l).mean()), -23.9),
        "Average lowest recorded WCT over land (degF)": (float(seas_w.wct_min.where(e5l).mean()), -86.7),
        "Average Oct-Mar snow load, land excl. glacier/perennial (lb/ft2)": (float(seas_s.sl_mean.where(e5l).mean()), 13.8),
        "Average highest recorded snow load, same cells (lb/ft2)": (float(seas_s.sl_max.where(e5l).mean()), 42.9),
    }
    src_lines, src_ok = source_untouched(first or 0)
    ok = ok and src_ok

    md = [f"# AZCOT preprocess validation ({dt.datetime.now():%Y-%m-%d %H:%M})", "",
          "## Recomputed daily values vs source products (max abs difference over all cells and 182 days)", "",
          "| check | max diff | pass (abs <= 0.01, or relative <= 5e-5) |", "|---|---:|---|"]
    for k, v in checks.items():
        md.append(f"| {k} | {v:.2e} | {'yes' if passed(k, v) else 'NO'} |")
    md += ["", "## Seasonal coverages vs ERDC/CRREL TR-26-5 (informational; unweighted means over ERA5-Land cells)", "",
           "Differences come from dropping Feb 29 and from land/ice masking details; the report does not state its masks.", "",
           "| quantity | coverages | TR-26-5 |", "|---|---:|---:|"]
    md += [f"| {k} | {a:.2f} | {b} |" for k, (a, b) in report.items()]
    counts = {int(c): int((st == c).sum()) for c in range(4)}
    md += ["", "## surface_type", "", f"cell counts (0 ocean, 1 land, 2 glacier, 3 perennial snow): {counts}",
           "", "## Source data integrity", ""] + src_lines
    md += ["", f"**Overall: {'PASS' if ok else 'FAIL'}**"]
    text = "\n".join(md)
    out_path("validation", "validation_report.md").write_text(text + "\n")
    print(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
