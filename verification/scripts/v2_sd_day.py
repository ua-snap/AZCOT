"""V2: scan every raw ERA5-Land snow-depth file (disk1/data/*/*/YYMMDDHH.SD.nc) for one calendar day (issues 5 and 6).

Usage: python v2_sd_day.py <day_index 0..182>

Per file: does it exist, how many non-NaN cells, and its own forecast reference time / step / valid time.
Per cell (0.1 deg grid, Metrics orientation = latitude ascending): number of valid hours, sum and max of depth (inches),
and counts of hours >= 8, 15, 20, 40 inches (SR-25-2 Table 3 thresholds). Output: OUT/sd/<mon>_<dd>.npz
"""
import os
import sys
import time
from datetime import datetime, timezone

import netCDF4
import numpy as np

from common import M_TO_IN, MONTH_NUM, OUT, all_days, ensure_dir, raw_path, years_for_day

SD_THR = [8, 15, 20, 40]
LAT_SD = np.round(60.0 + 0.1 * np.arange(301), 1)
LON_SD = np.round(-180.0 + 0.1 * np.arange(3600), 1)


def main():
    mon, dd = all_days()[int(sys.argv[1])]
    ys = years_for_day(mon, dd)
    t0 = time.time()
    n_valid = np.zeros((301, 3600), np.uint16)
    s = np.zeros((301, 3600))
    mx = np.full((301, 3600), -np.inf)
    cnt = np.zeros((len(SD_THR), 301, 3600), np.uint16)
    rec = {k: np.zeros((len(ys), 24)) for k in ("exists", "nonnan", "ref_time", "step_h", "valid_ok")}
    for iy, y in enumerate(ys):
        for h in range(24):
            p = raw_path(mon, dd, y, h, "SD")
            if not os.path.exists(p):
                continue
            rec["exists"][iy, h] = 1
            with netCDF4.Dataset(p, "r") as ds:
                lat = np.asarray(ds["latitude"][:])
                lon = np.asarray(ds["longitude"][:])
                if not (np.allclose(lat, LAT_SD[::-1]) and np.allclose(lon, LON_SD)):
                    raise ValueError(f"unexpected grid {p}")
                v = ds["sde"]
                v.set_auto_mask(False)
                a = np.asarray(v[:], np.float64)[::-1, :]
                rec["ref_time"][iy, h] = float(ds["time"][:])
                rec["step_h"][iy, h] = float(ds["step"][:])
                vt = float(ds["valid_time"][:])
            want = datetime(y, MONTH_NUM[mon], dd, h, tzinfo=timezone.utc).timestamp()
            rec["valid_ok"][iy, h] = vt == want
            ok = np.isfinite(a)
            rec["nonnan"][iy, h] = ok.sum()
            a_in = a * M_TO_IN
            n_valid += ok
            s += np.where(ok, a_in, 0.0)
            mx = np.where(ok & (a_in > mx), a_in, mx)
            for k, t in enumerate(SD_THR):
                cnt[k] += ok & (a_in >= t)
    mx[np.isinf(mx)] = np.nan
    out = dict(mon=mon, dd=dd, years=np.array(ys), n_valid=n_valid, sum_in=s.astype(np.float64), max_in=mx.astype(np.float32),
               count_ge=cnt, thr=np.array(SD_THR), **{f"file_{k}": v for k, v in rec.items()})
    path = f"{ensure_dir(OUT + '/sd')}/{mon}_{dd:02d}.npz"
    np.savez(path + ".tmp.npz", **out)
    os.replace(path + ".tmp.npz", path)
    print(f"{mon} {dd:02d}: {time.time() - t0:.0f}s, files {int(rec['exists'].sum())}, all-NaN "
          f"{int(((rec['nonnan'] == 0) & (rec['exists'] == 1)).sum())}", flush=True)


if __name__ == "__main__":
    main()
