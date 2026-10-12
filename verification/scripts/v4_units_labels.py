"""V4: independent checks of wind units and temperature labels (issues 4 and 10).

A) For one random (year, hour) on each of the 183 days (seeded), full grid:
   - WS10_knots.nc vs hypot(10U.grib, 10V.grib) (GRIB units m/s): which factor links them?
   - 2T.nc vs 2T.grib ('2t') and SKT.nc vs SKT.grib ('skt').
   - WCT.nc vs NWS formula from SKT.grib / 2T.grib and GRIB winds (mph).
B) Against the independent AKCASC ERA5 copy (global monthly files) for 00 UTC on a sample of days, since AKCASC skt is
   00 UTC only: t2m vs 2T.nc, skt vs SKT.nc (and the swapped pairings), u10/v10 vs the GRIB winds, and WCT.nc vs the
   NWS formula computed purely from AKCASC fields.
Writes verification/tables/v4_units_labels.csv and prints a summary.
"""
import os

import netCDF4
import numpy as np
import pandas as pd

from common import (AKCASC, KN_TO_MPH, MONTH_NUM, MS_TO_KN, NLAT, all_days, grib_path, k_to_f, raw_path, read_grib,
                    read_raw, wct_nws, years_for_day)

HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(20261012)


def akcasc(var, y, m, d, h):
    """One hourly (or daily 00 UTC for skt) field from AKCASC, cut to 60-90N and rolled to -180..179.75, Metrics order."""
    f = f"{AKCASC}/{var}/reanalysis-era5-single-levels_{var}_{y}_{m:02d}.nc"
    with netCDF4.Dataset(f, "r") as ds:
        tn = "time" if "time" in ds.variables else "valid_time"
        t = netCDF4.num2date(ds[tn][:], ds[tn].units)
        idx = [i for i, x in enumerate(t) if (x.year, x.month, x.day, x.hour) == (y, m, d, h)]
        if len(idx) != 1:
            raise ValueError(f"time not found in {f}")
        lat = np.asarray(ds["latitude"][:NLAT])
        lon = np.asarray(ds["longitude"][:])
        assert np.allclose(lat, 90 - 0.25 * np.arange(NLAT)) and np.allclose(lon, 0.25 * np.arange(1440))
        v = ds[var]
        a = np.asarray(v[idx[0], :NLAT, :], np.float64)
        sf = getattr(v, "scale_factor", 0.0)
    a = np.roll(a, -720, axis=1)            # 0..359.75 -> -180..179.75
    return a[::-1, :], sf


def main():
    rows = []
    for mon, dd in all_days():
        ys = years_for_day(mon, dd)
        y = int(rng.choice(ys))
        h = int(rng.integers(0, 24))
        u = read_grib(grib_path(mon, dd, y, h, "10U"), "10u", y, mon, dd, h)
        v = read_grib(grib_path(mon, dd, y, h, "10V"), "10v", y, mon, dd, h)
        t2g = read_grib(grib_path(mon, dd, y, h, "2T"), "2t", y, mon, dd, h)
        skg = read_grib(grib_path(mon, dd, y, h, "SKT"), "skt", y, mon, dd, h)
        ws, _ = read_raw(raw_path(mon, dd, y, h, "WS10_knots"), "WS10")
        t2n, _ = read_raw(raw_path(mon, dd, y, h, "2T"), "2T_GDS0_SFC")
        skn, _ = read_raw(raw_path(mon, dd, y, h, "SKT"), "SKT_GDS0_SFC")
        wc, _ = read_raw(raw_path(mon, dd, y, h, "WCT"), "WCT")
        sp = np.hypot(u, v)
        big = sp > 1.0
        mph = sp * MS_TO_KN * KN_TO_MPH
        rows.append(dict(
            part="A_grib", mon=mon, dd=dd, year=y, hour=h,
            ws_ratio_median=np.median(ws[big] / sp[big]), ws_ratio_min=(ws[big] / sp[big]).min(),
            ws_ratio_max=(ws[big] / sp[big]).max(),
            ws_vs_knots_maxabs=np.abs(ws - sp * MS_TO_KN).max(), ws_vs_ms_maxabs=np.abs(ws - sp).max(),
            t2_nc_vs_grib_maxabs=np.abs(t2n - t2g).max(), skt_nc_vs_grib_maxabs=np.abs(skn - skg).max(),
            wct_vs_skt_grib_maxabs=np.abs(wc - wct_nws(k_to_f(skg), mph)).max(),
            wct_vs_2t_grib_maxabs=np.abs(wc - wct_nws(k_to_f(t2g), mph)).max(),
            wct_vs_2t_grib_median=np.median(np.abs(wc - wct_nws(k_to_f(t2g), mph))),
        ))
    # B) AKCASC at 00 UTC: 3 days per month x 6 months, random year each
    for mon in ["oct", "nov", "dec", "jan", "feb", "mar"]:
        for dd in (5, 15, 25):
            y = int(rng.choice(years_for_day(mon, dd)))
            m = MONTH_NUM[mon]
            h = 0
            t2a, sft = akcasc("t2m", y, m, dd, h)
            ska, sfs = akcasc("skt", y, m, dd, h)
            ua, sfu = akcasc("u10", y, m, dd, h)
            va, sfv = akcasc("v10", y, m, dd, h)
            t2n, _ = read_raw(raw_path(mon, dd, y, h, "2T"), "2T_GDS0_SFC")
            skn, _ = read_raw(raw_path(mon, dd, y, h, "SKT"), "SKT_GDS0_SFC")
            wc, _ = read_raw(raw_path(mon, dd, y, h, "WCT"), "WCT")
            ws, _ = read_raw(raw_path(mon, dd, y, h, "WS10_knots"), "WS10")
            u = read_grib(grib_path(mon, dd, y, h, "10U"), "10u", y, mon, dd, h)
            v = read_grib(grib_path(mon, dd, y, h, "10V"), "10v", y, mon, dd, h)
            mph_a = np.hypot(ua, va) * MS_TO_KN * KN_TO_MPH
            rows.append(dict(
                part="B_akcasc", mon=mon, dd=dd, year=y, hour=h,
                t2m_scale=sft, skt_scale=sfs, u10_scale=sfu,
                akc_t2m_vs_2Tnc_maxabs=np.abs(t2a - t2n).max(), akc_skt_vs_SKTnc_maxabs=np.abs(ska - skn).max(),
                akc_t2m_vs_SKTnc_median=np.median(np.abs(t2a - skn)), akc_skt_vs_2Tnc_median=np.median(np.abs(ska - t2n)),
                akc_u10_vs_grib_maxabs=np.abs(ua - u).max(), akc_v10_vs_grib_maxabs=np.abs(va - v).max(),
                ws_vs_akc_knots_maxabs=np.abs(ws - np.hypot(ua, va) * MS_TO_KN).max(),
                wct_vs_akc_skt_maxabs=np.abs(wc - wct_nws(k_to_f(ska), mph_a)).max(),
                wct_vs_akc_t2m_median=np.median(np.abs(wc - wct_nws(k_to_f(t2a), mph_a))),
                wct_vs_akc_t2m_frac005=np.mean(np.abs(wc - wct_nws(k_to_f(t2a), mph_a)) < 0.05),
            ))
        print("done", mon, flush=True)
    df = pd.DataFrame(rows)
    out = os.path.join(HERE, "..", "tables", "v4_units_labels.csv")
    df.to_csv(out, index=False, float_format="%.6g")
    a = df[df.part == "A_grib"]
    b = df[df.part == "B_akcasc"]
    pd.set_option("display.width", 200)
    print(f"A) {len(a)} hours vs GRIB:")
    print(a.drop(columns=["part", "mon", "dd", "year", "hour"]).describe().loc[["min", "50%", "max"]].T)
    print(f"B) {len(b)} hours vs AKCASC:")
    print(b.drop(columns=["part", "mon", "dd", "year", "hour"]).dropna(axis=1, how="all").describe().loc[["min", "50%", "max"]].T)


if __name__ == "__main__":
    main()
