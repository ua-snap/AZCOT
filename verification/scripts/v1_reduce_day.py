"""V1: reduce one calendar day of raw hourly AZCOT data to every statistic needed to test issues 1-4, 7 and 10.

Usage: python v1_reduce_day.py <day_index 0..182>   (or --mon jan --day 15)

Reads (read-only) for each of the 30 (or 8) years x 24 hours:
  2T.nc (K), SKT.nc (K), WCT.nc (degF), WS10_knots.nc (kn), SWE.grib (m w.e.)
Per hour it records: NaN counts, the file's own initial_time / parameter_number, and how well WCT.nc is reproduced
by the NWS formula from SKT or from 2T (TR-26-5 eq. 3).
Per cell it stores candidate statistics (true min/max, mean of annual extremes, sum of annual extremes / 30,
percentiles, threshold counts, consecutive-run sums, per-hour-of-day minima) in OUT/daily/<mon>_<dd>.npz.
"""
import argparse
import os
import sys
import time

import numpy as np

from common import (KN_TO_MPH, MONTH_NUM, NLAT, NLON, OUT, SWE_M_TO_LBFT2, WINDOWS, all_days, ensure_dir, grib_path, k_to_f,
                    raw_path, read_grib, read_raw, wct_nws, years_for_day)

WCT_THR = list(range(0, -101, -5))          # Metrics WCT frequency thresholds
T_THR = list(range(0, -76, -5))             # 2T / consecutive thresholds (degF)
WS_THR = [8, 13, 15, 20, 25, 26, 30, 35, 40, 45, 50]


def runs_stats(b):
    """b: bool (24, ...) for one year. Returns (mean run length, mean run length ignoring 1-hour runs), 0 if no run."""
    prev = np.zeros_like(b[0])
    starts = np.zeros(b.shape[1:], np.int32)
    ones = np.zeros(b.shape[1:], np.int32)
    total = b.sum(0).astype(np.int32)
    for h in range(24):
        nxt = b[h + 1] if h < 23 else np.zeros_like(b[0])
        s = b[h] & ~prev
        starts += s
        ones += s & ~nxt
        prev = b[h]
    with np.errstate(invalid="ignore", divide="ignore"):
        m = np.where(starts > 0, total / np.maximum(starts, 1), 0.0)
        m1 = np.where(starts - ones > 0, (total - ones) / np.maximum(starts - ones, 1), 0.0)
    return m, m1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("index", nargs="?", type=int)
    ap.add_argument("--mon")
    ap.add_argument("--day", type=int)
    a = ap.parse_args()
    mon, dd = (a.mon, a.day) if a.mon else all_days()[a.index]
    ys = years_for_day(mon, dd)
    ny = len(ys)
    t0 = time.time()

    shp = (ny, 24, NLAT, NLON)
    T2 = np.empty(shp, np.float32)     # K
    SK = np.empty(shp, np.float32)     # K
    WC = np.empty(shp, np.float32)     # degF as stored
    WS = np.empty(shp, np.float32)     # kn
    SL = np.empty(shp, np.float32)     # lb/ft2 from SWE
    W2 = np.empty(shp, np.float32)     # WCT recomputed from 2T (eq. 3 as written)

    hourly = {k: np.zeros((ny, 24)) for k in [
        "nan_2T", "nan_SKT", "nan_WCT", "nan_WS", "nan_SWE",
        "wct_skt_maxabs", "wct_skt_frac001", "wct_2t_maxabs", "wct_2t_medabs", "wct_2t_frac005",
        "wct_skt_knots_as_mph_maxabs", "time_ok_2T", "time_ok_SKT"]}

    for iy, y in enumerate(ys):
        for h in range(24):
            t2, it2 = read_raw(raw_path(mon, dd, y, h, "2T"), "2T_GDS0_SFC")
            sk, its = read_raw(raw_path(mon, dd, y, h, "SKT"), "SKT_GDS0_SFC")
            wc, _ = read_raw(raw_path(mon, dd, y, h, "WCT"), "WCT")
            ws, _ = read_raw(raw_path(mon, dd, y, h, "WS10_knots"), "WS10")
            swe = read_grib(grib_path(mon, dd, y, h, "SWE"), "sd", y, mon, dd, h)   # checks date/time/param/grid
            # the netCDF file's own time stamp, e.g. '01/15/2000 (12:00)'
            want = f"{MONTH_NUM[mon]:02d}/{dd:02d}/{y} ({h:02d}:00)"
            hourly["time_ok_2T"][iy, h] = it2 == want
            hourly["time_ok_SKT"][iy, h] = its == want
            for k, v in (("nan_2T", t2), ("nan_SKT", sk), ("nan_WCT", wc), ("nan_WS", ws), ("nan_SWE", swe)):
                hourly[k][iy, h] = np.isnan(v).sum()

            v_mph = ws * KN_TO_MPH
            w_skt = wct_nws(k_to_f(sk), v_mph)
            w_2t = wct_nws(k_to_f(t2), v_mph)
            w_knots = wct_nws(k_to_f(sk), ws)
            d1 = np.abs(wc - w_skt)
            d2 = np.abs(wc - w_2t)
            hourly["wct_skt_maxabs"][iy, h] = np.nanmax(d1)
            hourly["wct_skt_frac001"][iy, h] = np.mean(d1 < 0.01)
            hourly["wct_2t_maxabs"][iy, h] = np.nanmax(d2)
            hourly["wct_2t_medabs"][iy, h] = np.nanmedian(d2)
            hourly["wct_2t_frac005"][iy, h] = np.mean(d2 < 0.05)
            hourly["wct_skt_knots_as_mph_maxabs"][iy, h] = np.nanmax(np.abs(wc - w_knots))

            T2[iy, h], SK[iy, h], WC[iy, h], WS[iy, h] = t2, sk, wc, ws
            SL[iy, h] = swe * SWE_M_TO_LBFT2
            W2[iy, h] = w_2t
    t_read = time.time() - t0

    out = {"mon": mon, "dd": dd, "years": np.array(ys), "n_years": ny}
    out.update({f"hourly_{k}": v for k, v in hourly.items()})

    def extremes(name, X, kind):
        f = np.min if kind == "min" else np.max
        ann = f(X, axis=1)                                 # (ny, lat, lon) annual extreme for this day
        out[f"{name}_true_{kind}"] = f(ann, axis=0)
        out[f"{name}_meanann_{kind}"] = ann.mean(0, dtype=np.float64).astype(np.float32)
        out[f"{name}_sum30_{kind}"] = (ann.sum(0, dtype=np.float64) / 30.0).astype(np.float32)
        for w, (h0, h1) in enumerate(WINDOWS):
            annw = f(X[:, h0:h1 + 1], axis=1)
            out[f"{name}_w{w}_true_{kind}"] = f(annw, axis=0)
            out[f"{name}_w{w}_meanann_{kind}"] = annw.mean(0, dtype=np.float64).astype(np.float32)
        return ann

    for name, X in (("T2", T2), ("SKT", SK), ("WCT", WC), ("WCT2T", W2)):
        ann = extremes(name, X, "min")
        out[f"{name}_mean"] = X.mean((0, 1), dtype=np.float64).astype(np.float32)
        flat = X.reshape(ny * 24, NLAT, NLON)
        out[f"{name}_p1"] = np.percentile(flat, 1, axis=0).astype(np.float32)   # numpy 'linear' == pandas quantile
        out[f"{name}_p5"] = np.percentile(flat, 5, axis=0).astype(np.float32)
        out[f"{name}_hourmin"] = X.min(0)                                       # (24, lat, lon) min over years per UTC hour
        if name in ("T2", "WCT"):
            out[f"{name}_annmin"] = ann                                         # (ny, lat, lon)
    for name, X in (("WS", WS), ("SL", SL)):
        extremes(name, X, "max")
        extremes(name, X, "min")
        out[f"{name}_mean"] = X.mean((0, 1), dtype=np.float64).astype(np.float32)

    # threshold counts (<= for temperatures, >= for wind) over the whole day and per 6-h window
    T2F = k_to_f(T2.astype(np.float64)).astype(np.float32)
    SKF = k_to_f(SK.astype(np.float64)).astype(np.float32)
    for name, X, thr in (("WCT", WC, WCT_THR), ("WCT2T", W2, WCT_THR), ("T2F", T2F, T_THR), ("SKTF", SKF, T_THR)):
        out[f"{name}_count_le"] = np.stack([(X <= t).sum((0, 1)) for t in thr]).astype(np.uint16)
        out[f"{name}_thr"] = np.array(thr)
        if name == "T2F":
            out["T2F_w_count_le"] = np.stack([np.stack([(X[:, h0:h1 + 1] <= t).sum((0, 1)) for t in thr])
                                              for h0, h1 in WINDOWS]).astype(np.uint16)
    out["T2K_count_le"] = np.stack([(T2 <= t).sum((0, 1)) for t in T_THR]).astype(np.uint16)   # thresholds applied to kelvin
    out["WS_count_ge"] = np.stack([(WS >= t).sum((0, 1)) for t in WS_THR]).astype(np.uint16)
    out["WS_thr"] = np.array(WS_THR)

    # consecutive-run metrics: per year mean run length (and without 1-h runs), summed over years
    for name, X in (("WCT", WC), ("T2F", T2F), ("T2K", T2)):
        s = np.zeros((len(T_THR), NLAT, NLON))
        s1 = np.zeros_like(s)
        for k, t in enumerate(T_THR):
            for iy in range(ny):
                m, m1 = runs_stats(X[iy] <= t)
                s[k] += m
                s1[k] += m1
        out[f"{name}_consec_sum"] = s.astype(np.float32)
        out[f"{name}_consec1_sum"] = s1.astype(np.float32)

    # inversion / SKT-vs-2T diagnostics (sums over all hours, so seasons can be pooled exactly)
    out["sum_skt_minus_2t"] = (SKF.astype(np.float64) - T2F).sum((0, 1)).astype(np.float32)
    out["sum_wct_minus_wct2t"] = (WC.astype(np.float64) - W2).sum((0, 1)).astype(np.float32)
    out["sum_ws"] = WS.sum((0, 1), dtype=np.float64).astype(np.float32)
    calm = WS < 5.0
    out["n_calm"] = calm.sum((0, 1)).astype(np.uint16)
    out["sum_skt_minus_2t_calm"] = np.where(calm, SKF.astype(np.float64) - T2F, 0).sum((0, 1)).astype(np.float32)
    out["n_hours"] = ny * 24

    path = f"{ensure_dir(OUT + '/daily')}/{mon}_{dd:02d}.npz"
    np.savez(path + ".tmp.npz", **out)
    os.replace(path + ".tmp.npz", path)
    print(f"{mon} {dd:02d}: {ny} yrs, read {t_read:.0f}s, total {time.time() - t0:.0f}s -> {path}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
