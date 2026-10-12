"""V5: issues 5 and 6 from the V2 snow-depth scan.

Issue 5: which raw SD files are all-NaN (and their forecast reference time / step); cross-check month-end 12 UTC against the
independent AKCASC ERA5-Land copy (daily 12 UTC sde).
Issue 6: Metrics daily_SD_stats frequency_X vs count/720 (missing counted as "not exceeding") vs count/n_valid;
averageSL (SD mean) and max_SD vs raw.
Writes verification/tables/v5_sd_files.csv (one row per all-NaN file), v5_sd_daily.csv (one row per day) and
OUT/misc/v5_sd_monthly.npz (monthly mean frequencies, Metrics vs corrected).
"""
import glob
import os
from datetime import datetime, timezone

import netCDF4
import numpy as np
import pandas as pd

from common import M_TO_IN, MET, MONTHS, OUT, all_days

HERE = os.path.dirname(os.path.abspath(__file__))
TAB = os.path.join(HERE, "..", "tables")
TOL = 1e-3


def read_met_sd(mon, dd):
    with netCDF4.Dataset(f"{MET}/daily_SD_stats/{mon}_{dd:02d}_SD_stats.nc", "r") as ds:
        lat = np.asarray(ds["latitude"][:])
        assert np.allclose(lat, np.round(60 + 0.1 * np.arange(301), 1))   # Metrics SD is ascending
        out = {}
        for k in ("averageSL", "max_SD", "frequency_8", "frequency_15", "frequency_20", "frequency_40"):
            v = ds[k]
            v.set_auto_mask(False)
            out[k] = np.asarray(v[:], np.float64)
    return out


def main():
    files, days = [], []
    monthly = {m: {"met": 0, "fix": 0, "n": 0} for m in MONTHS}
    land = None
    for mon, dd in all_days():
        z = np.load(f"{OUT}/sd/{mon}_{dd:02d}.npz")
        ys = z["years"]
        ex, nn = z["file_exists"], z["file_nonnan"]
        for iy, y in enumerate(ys):
            for h in range(24):
                if ex[iy, h] == 0 or nn[iy, h] == 0:
                    ref = datetime.fromtimestamp(z["file_ref_time"][iy, h], tz=timezone.utc)
                    files.append(dict(mon=mon, dd=dd, year=int(y), hour=h, exists=int(ex[iy, h]),
                                      ref_time=ref.strftime("%Y-%m-%d %H"), step_h=z["file_step_h"][iy, h],
                                      valid_ok=int(z["file_valid_ok"][iy, h])))
        nv = z["n_valid"].astype(np.float64)
        nh = len(ys) * 24
        m = read_met_sd(mon, dd)
        if land is None:
            land = np.isfinite(m["averageSL"])
        r = dict(mon=mon, dd=dd, files=int(ex.sum()), allnan_files=int(((nn == 0) & (ex == 1)).sum()),
                 valid_ok_all=bool(z["file_valid_ok"][ex == 1].all()),
                 nonnan_counts=" ".join(str(int(x)) for x in np.unique(nn[nn > 0])))
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_raw = z["sum_in"] / nv
        ok = land & (nv > 0)
        # averageSL / max_SD are stored in METRES (frequencies use inch thresholds); compare in metres
        r["mean_m_vs_raw_maxabs"] = float(np.abs(m["averageSL"][ok] - mean_raw[ok] / M_TO_IN).max())
        r["max_m_vs_raw_maxabs"] = float(np.abs(m["max_SD"][ok] - z["max_in"][ok] / M_TO_IN).max())
        for k, t in enumerate(z["thr"]):
            c = z["count_ge"][k].astype(np.float64)
            met = m[f"frequency_{t}"]
            f720 = c / nh * 100
            with np.errstate(invalid="ignore", divide="ignore"):
                fvalid = c / nv * 100
            d720 = np.abs(met[ok] - f720[ok])
            r[f"f{t}_vs_div720_maxabs"] = float(d720.max())
            r[f"f{t}_vs_divvalid_maxabs"] = float(np.abs(met[ok] - fvalid[ok]).max())
            r[f"f{t}_rebuilt_vs_divvalid_maxabs"] = float(np.abs(met[ok] * nh / nv[ok] - fvalid[ok]).max())
            r[f"f{t}_land_mean_met"] = float(np.mean(met[ok]))
            r[f"f{t}_land_mean_fixed"] = float(np.mean(fvalid[ok]))
            if t == 8:
                monthly[mon]["met"] = monthly[mon]["met"] + np.where(ok, met, 0)
                monthly[mon]["fix"] = monthly[mon]["fix"] + np.where(ok, fvalid, 0)
                monthly[mon]["n"] += 1
        days.append(r)
        print(mon, dd, flush=True)
    fdf = pd.DataFrame(files)
    fdf.to_csv(os.path.join(TAB, "v5_sd_files.csv"), index=False)
    pd.DataFrame(days).to_csv(os.path.join(TAB, "v5_sd_daily.csv"), index=False, float_format="%.6g")
    np.savez(f"{OUT}/misc/v5_sd_monthly.npz", land=land,
             **{f"{m}_{k}": monthly[m][k] / monthly[m]["n"] for m in MONTHS for k in ("met", "fix")})
    print(fdf.groupby("mon").size())
    print(fdf.groupby(["hour"]).size().to_string())
    print(fdf.groupby("dd").size())


if __name__ == "__main__":
    main()
