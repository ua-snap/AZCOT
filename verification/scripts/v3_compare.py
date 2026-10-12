"""V3: compare Metrics and Atlas fields with the V1 raw-data reductions, for all 183 days (issues 1-4, 7, 10).

Writes one row per day to verification/tables/v3_<topic>.csv and season accumulators to OUT/misc/v3_season.npz.
Optional args: day indices to process (for testing); default all 183.
Tolerances: values are float32 in the files; "equal" means |diff| <= TOL (1e-3 in the variable's own units).
"""
import os
import sys

import numpy as np
import pandas as pd

from common import ATLAS, MET, OUT, SITES, WINDOWS, all_days, cell, ensure_dir, k_to_f, metrics_vars, read_atlas_tif, read_metrics

HERE = os.path.dirname(os.path.abspath(__file__))
TAB = os.path.join(HERE, "..", "tables")
TOL = 1e-3
T_THR = list(range(0, -76, -5))
WCT_THR = list(range(0, -101, -5))
WS_THR = [8, 13, 15, 20, 25, 26, 30, 35, 40, 45, 50]


def cmp(a, b, mask=None):
    """max |a-b| and share of cells with |a-b| <= TOL, over cells where both are finite (and mask)."""
    ok = np.isfinite(a) & np.isfinite(b)
    if mask is not None:
        ok &= mask
    d = np.abs(a[ok] - b[ok])
    return (float(d.max()) if d.size else np.nan), (float(np.mean(d <= TOL)) if d.size else np.nan), int(ok.sum())


def six_h(mon, dd, var, w):
    h0, h1 = WINDOWS[w]
    return f"{MET}/6h_{var}_stats/{mon}_{dd:02d}_6h_{h0}through{h1}_{var}_stats.nc"


def main():
    rows = {k: [] for k in ("issue1", "issue3", "issue4", "issue7", "issue10", "consec")}
    land = None
    season = {}
    days = all_days()
    part = None
    if len(sys.argv) > 1 and sys.argv[1] == "--part":          # --part k n: every n-th day starting at k
        part, nparts = int(sys.argv[2]), int(sys.argv[3])
        days = days[part::nparts]
    elif len(sys.argv) > 1:
        days = [days[int(x)] for x in sys.argv[1:]]
    for mon, dd in days:
        z = np.load(f"{OUT}/daily/{mon}_{dd:02d}.npz")
        ny = int(z["n_years"])
        nh = int(z["n_hours"])
        tag = dict(mon=mon, dd=dd, n_years=ny)

        # ---------------- issue 1 / 2: daily and 6-h minima ----------------
        mw = read_metrics(f"{MET}/daily_WCT_stats/{mon}_{dd:02d}_WCT_stats.nc",
                          ["min_WCT", "averageTemp", "percentile_1"] + [f"consecutive_{t}" for t in T_THR]
                          + [f"consecutive_{t}_no_ones" for t in T_THR])
        m2 = read_metrics(f"{MET}/daily_2T_stats/{mon}_{dd:02d}_2T_stats.nc",
                          ["min_2T", "averageTemp", "percentile_1"] + [f"frequency_{t}" for t in T_THR]
                          + [f"consecutive_{t}" for t in T_THR] + [f"consecutive_{t}_no_ones" for t in T_THR])
        ms = read_metrics(f"{MET}/daily_SKT_stats/{mon}_{dd:02d}_SKT_stats.nc", ["min_SKT", "averageSKT"])
        r = dict(tag)
        for lab, M, key, pre in (("WCT", mw, "min_WCT", "WCT"), ("2T", m2, "min_2T", "T2"), ("SKT", ms, "min_SKT", "SKT")):
            for cand in ("true_min", "meanann_min", "sum30_min"):
                mx, fr, n = cmp(M[key], z[f"{pre}_{cand}"])
                r[f"{lab}_vs_{cand}_maxabs"], r[f"{lab}_vs_{cand}_fracEq"] = mx, fr
            r[f"{lab}_ncells"] = n
        ok = np.isfinite(mw["min_WCT"]) & np.isfinite(mw["percentile_1"])
        r["WCT_n_min_le_p1"] = int((mw["min_WCT"][ok] <= mw["percentile_1"][ok]).sum())
        r["WCT_p1_vs_raw_maxabs"] = cmp(mw["percentile_1"], z["WCT_p1"])[0]
        r["WCT_avg_vs_raw_maxabs"] = cmp(mw["averageTemp"], z["WCT_mean"])[0]
        d = mw["min_WCT"] - z["WCT_true_min"]
        r["WCT_minus_truemin_mean"] = float(np.nanmean(d))
        r["WCT_minus_truemin_max"] = float(np.nanmax(d))
        r["WCT_minus_truemin_min"] = float(np.nanmin(d))
        # 6-h files (frequency script only)
        for w in range(4):
            v6 = metrics_vars(six_h(mon, dd, "WCT", w))
            k6 = [k for k in v6 if k.lower().startswith("min")]
            r[f"WCT6h_w{w}_var"] = k6[0] if k6 else "NONE:" + "|".join(k for k in v6 if not k.startswith(("frequency", "percentile", "g0_")))
            if k6:
                a = read_metrics(six_h(mon, dd, "WCT", w), [k6[0]])[k6[0]]
                r[f"WCT6h_w{w}_vs_true_maxabs"] = cmp(a, z[f"WCT_w{w}_true_min"])[0]
                r[f"WCT6h_w{w}_vs_meanann_maxabs"] = cmp(a, z[f"WCT_w{w}_meanann_min"])[0]
            a = read_metrics(six_h(mon, dd, "2T", w), ["min_2T"])["min_2T"]
            r[f"T26h_w{w}_vs_true_maxabs"] = cmp(a, z[f"T2_w{w}_true_min"])[0]
            v6 = metrics_vars(six_h(mon, dd, "SKT", w))
            k6 = [k for k in v6 if k.lower().startswith("min")]
            if k6:
                a = read_metrics(six_h(mon, dd, "SKT", w), [k6[0]])[k6[0]]
                r[f"SKT6h_w{w}_vs_true_maxabs"] = cmp(a, z[f"SKT_w{w}_true_min"])[0]
        rows["issue1"].append(r)

        # consecutive (all days): Metrics == sum over years / 30 ?
        r = dict(tag)
        for k, t in enumerate(T_THR):
            for M, pre, lab in ((mw, "WCT", "WCT"),):
                r[f"{lab}_c{t}_vs_sum30"] = cmp(M[f"consecutive_{t}"], z[f"{pre}_consec_sum"][k] / 30.0)[0]
                r[f"{lab}_c{t}_vs_mean"] = cmp(M[f"consecutive_{t}"], z[f"{pre}_consec_sum"][k] / ny)[0]
                r[f"{lab}_c{t}no1_vs_sum30"] = cmp(M[f"consecutive_{t}_no_ones"], z[f"{pre}_consec1_sum"][k] / 30.0)[0]
        rows["consec"].append(r)

        # ---------------- issue 3: 2T kelvin / degF thresholds ----------------
        r = dict(tag)
        r["avg_vs_rawK_maxabs"] = cmp(m2["averageTemp"], z["T2_mean"])[0]
        r["p1_vs_rawK_maxabs"] = cmp(m2["percentile_1"], z["T2_p1"])[0]
        r["avg_min_K"] = float(np.nanmin(m2["averageTemp"]))
        r["freq_all_zero"] = bool(all(np.nanmax(np.abs(m2[f"frequency_{t}"])) == 0 for t in T_THR))
        r["freq_nan_cells"] = int(sum(np.isnan(m2[f"frequency_{t}"]).sum() for t in T_THR))
        r["consec_all_zero"] = bool(all(np.nanmax(np.abs(m2[f"consecutive_{t}"])) == 0 and
                                        np.nanmax(np.abs(m2[f"consecutive_{t}_no_ones"])) == 0 for t in T_THR))
        # are the 2T consecutive fields the correct degF values? (share of cells equal; ties at a threshold can differ)
        eqs = [cmp(m2[f"consecutive_{t}"], z["T2F_consec_sum"][k] / 30.0)[1] for k, t in enumerate(T_THR)]
        r["consec_vs_degF_fracEq_min"] = float(min(eqs))
        r["consec_vs_degF_maxabs"] = max(cmp(m2[f"consecutive_{t}"], z["T2F_consec_sum"][k] / 30.0)[0]
                                         for k, t in enumerate(T_THR))
        r["rawK_counts_all_zero"] = bool(z["T2K_count_le"].max() == 0)
        r["rawK_consec_all_zero"] = bool(z["T2K_consec_sum"].max() == 0)
        for t in (-20, -40, -65):
            k = T_THR.index(t)
            r[f"true_freq{t}_cells_gt0"] = int((z["T2F_count_le"][k] > 0).sum())
            r[f"true_freq{t}_max"] = float(z["T2F_count_le"][k].max() / nh * 100)
        z6 = True
        eq6 = []
        for w in range(4):
            m6 = read_metrics(six_h(mon, dd, "2T", w), [f"frequency_{t}" for t in T_THR] + ["avg_2T"])
            z6 &= all(np.nanmax(np.abs(m6[f"frequency_{t}"])) == 0 for t in T_THR)
            eq6 += [cmp(m6[f"frequency_{t}"], z["T2F_w_count_le"][w, k] / (ny * 6) * 100)[1] for k, t in enumerate(T_THR)]
            r[f"avg6h_w{w}_min"] = float(np.nanmin(m6["avg_2T"]))
        r["freq6h_all_zero"] = bool(z6)
        r["freq6h_vs_degF_fracEq_min"] = float(min(eq6))
        # Atlas 2T frequency rasters: are they the correct (degF) frequencies?
        worst, eqa = 0.0, []
        for k, t in enumerate(T_THR):
            at = read_atlas_tif(f"{ATLAS}/{mon}/Daily/{dd:02d}/2T/Frequency/{mon}_{dd:02d}_2T_freq_{t}.tif")
            true = z["T2F_count_le"][k] / nh * 100
            mx, fr, n = cmp(at, true)
            worst = max(worst, mx)
            eqa.append(fr)
            if t == -40:
                r["atlas_freq-40_ncells"], r["atlas_freq-40_fracEq"], r["atlas_freq-40_max_val"] = n, fr, float(np.nanmax(at))
        r["atlas_freq_maxabs_all_thr"] = worst
        r["atlas_freq_fracEq_min_thr"] = float(min(eqa))
        rows["issue3"].append(r)

        # ---------------- issue 4: wind ----------------
        mwd = read_metrics(f"{MET}/daily_WSPD_stats/{mon}_{dd:02d}_WSPD_stats.nc",
                           ["max_WSPD", "min_WS10", "averageWSPD"] + [f"frequency_{t}" for t in WS_THR])
        r = dict(tag)
        r["max_eq_min_ws10_bitwise"] = bool(np.array_equal(mwd["max_WSPD"], mwd["min_WS10"], equal_nan=True))
        for key in ("max_WSPD", "min_WS10"):
            for cand in ("true_max", "meanann_max", "sum30_max", "true_min", "meanann_min"):
                mx, fr, _ = cmp(mwd[key], z[f"WS_{cand}"])
                r[f"{key}_vs_{cand}_maxabs"], r[f"{key}_vs_{cand}_fracEq"] = mx, fr
        r["avg_vs_raw_kn_maxabs"] = cmp(mwd["averageWSPD"], z["WS_mean"])[0]
        r["freq_vs_raw_ge_maxabs"] = max(cmp(mwd[f"frequency_{t}"], z["WS_count_ge"][k] / nh * 100)[0]
                                         for k, t in enumerate(WS_THR))
        for w in range(4):
            a = read_metrics(six_h(mon, dd, "WSPD", w), ["max_wspd"])["max_wspd"]
            r[f"ws6h_w{w}_vs_true_max"] = cmp(a, z[f"WS_w{w}_true_max"])[0]
        i, j = cell(*SITES["Fairbanks"])
        r["fairbanks_max_WSPD"], r["fairbanks_true_max"] = float(mwd["max_WSPD"][i, j]), float(z["WS_true_max"][i, j])
        rows["issue4"].append(r)

        # ---------------- issue 7: Atlas extreme rasters ----------------
        r = dict(tag)
        a2 = read_atlas_tif(f"{ATLAS}/{mon}/Daily/{dd:02d}/2T/Extreme/{mon}_{dd:02d}_2T_min.tif")
        aw = read_atlas_tif(f"{ATLAS}/{mon}/Daily/{dd:02d}/WCT/Extreme/{mon}_{dd:02d}_WCT_min.tif")
        if land is None:
            land = np.isfinite(aw)
        t2true = k_to_f(z["T2_true_min"].astype(np.float64))
        hm = k_to_f(z["T2_hourmin"].astype(np.float64))                # (24, lat, lon)
        ok = np.isfinite(a2)
        dlt = a2[ok] - t2true[ok]
        r["atlas2T_ncells"] = int(ok.sum())
        r["atlas2T_eq"] = float(np.mean(np.abs(dlt) <= TOL))
        r["atlas2T_warmer"] = float(np.mean(dlt > TOL))
        r["atlas2T_colder"] = float(np.mean(dlt < -TOL))
        r["atlas2T_diff_mean"] = float(dlt.mean())
        r["atlas2T_diff_max"] = float(dlt.max())
        below = (hm < a2[None] - TOL) & ok[None]                          # hours (any year) colder than the Atlas value
        r["atlas2T_hours_below"] = " ".join(str(h) for h in range(24) if below[h].any())
        hours_in = [h for h in range(24) if not below[h].any()]
        r["atlas2T_vs_min_of_hours_in_fracEq"] = cmp(a2, hm[hours_in].min(0))[1] if hours_in else np.nan
        for w in range(4):
            h0, h1 = WINDOWS[w]
            a6 = read_atlas_tif(f"{ATLAS}/{mon}/Six Hour/{dd:02d}/2T/Extreme/{mon}_{dd:02d}_6h_{h0}through{h1}_2T_min.tif")
            r[f"atlas2T6h_w{w}_fracEq_true"] = cmp(a6, k_to_f(z[f"T2_w{w}_true_min"].astype(np.float64)))[1]
        okw = np.isfinite(aw)
        r["atlasWCT_ncells"] = int(okw.sum())
        r["atlasWCT_vs_true_maxabs"], r["atlasWCT_fracEq"], _ = cmp(aw, z["WCT_true_min"])
        rows["issue7"].append(r)

        # ---------------- issue 10: SKT vs 2T wind chill (season accumulators) ----------------
        for key in ("WCT_count_le", "WCT2T_count_le"):
            season[key] = season.get(key, 0) + z[key].astype(np.int64)
        season["hours"] = season.get("hours", 0) + nh
        season["daily_freq65_skt"] = season.get("daily_freq65_skt", 0) + z["WCT_count_le"][WCT_THR.index(-65)] / nh * 100
        season["daily_freq65_2t"] = season.get("daily_freq65_2t", 0) + z["WCT2T_count_le"][WCT_THR.index(-65)] / nh * 100
        mf = read_metrics(f"{MET}/daily_WCT_stats/{mon}_{dd:02d}_WCT_stats.nc", ["frequency_-65"])["frequency_-65"]
        season["daily_freq65_metrics"] = season.get("daily_freq65_metrics", 0) + mf
        for key in ("sum_skt_minus_2t", "sum_wct_minus_wct2t", "sum_ws", "sum_skt_minus_2t_calm"):
            season[key] = season.get(key, 0) + z[key].astype(np.float64)
        season["n_calm"] = season.get("n_calm", 0) + z["n_calm"].astype(np.int64)
        season["wct_true_min"] = np.fmin(season.get("wct_true_min", np.inf), z["WCT_true_min"])
        season["wct2t_true_min"] = np.fmin(season.get("wct2t_true_min", np.inf), z["WCT2T_true_min"])
        season["sl_min"] = np.fmin(season.get("sl_min", np.inf), z["SL_true_min"])
        hr = {k[len("hourly_"):]: z[k] for k in z.files if k.startswith("hourly_")}
        r = dict(tag)
        r.update({f"{k}_max": float(v.max()) for k, v in hr.items()})
        r.update({f"{k}_min": float(v.min()) for k, v in hr.items()})
        rows["issue10"].append(r)
        print(mon, dd, flush=True)

    if part is not None:                                         # chunk outputs; v3_merge.py combines them
        d = ensure_dir(f"{OUT}/misc/v3parts")
        for k, v in rows.items():
            pd.DataFrame(v).to_csv(f"{d}/{k}_part{part:02d}.csv", index=False, float_format="%.6g")
        np.savez(f"{d}/season_part{part:02d}.npz", land=land, **{k: np.asarray(v) for k, v in season.items()})
        return
    for k, v in rows.items():
        pd.DataFrame(v).to_csv(os.path.join(TAB, f"v3_{k}.csv"), index=False, float_format="%.6g")
    np.savez(f"{OUT}/misc/v3_season.npz", land=land, **{k: np.asarray(v) for k, v in season.items()})
    print("wrote tables and season accumulators")


if __name__ == "__main__":
    main()
