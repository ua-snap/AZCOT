"""V9: extract the small per-day series the figures need (runs in the azcot-preprocess env; figures.py plots them).

Output OUT/misc/v9_figdata.npz with, for each of the 183 days:
  Fairbanks: raw true min WCT, mean of annual minima, 1st percentile, Metrics min_WCT, Atlas WCT min;
             raw true max wind, mean of annual maxima, Metrics max_WSPD;
             raw true min 2T (F), Atlas 2T min (F)
  land means (Atlas land mask): % hours 2T <= -40 F from raw, Metrics daily, Atlas daily raster;
             Metrics min_WCT minus raw true min
"""
import numpy as np

from common import ATLAS, MET, OUT, SITES, all_days, cell, k_to_f, read_atlas_tif, read_metrics

T_THR = list(range(0, -76, -5))


def main():
    i, j = cell(*SITES["Fairbanks"])
    keys = ["fb_wct_true", "fb_wct_meanann", "fb_wct_p1", "fb_wct_metrics", "fb_wct_atlas", "fb_ws_true", "fb_ws_meanann",
            "fb_ws_metrics", "fb_t2_true", "fb_t2_atlas", "land_f40_raw", "land_f40_metrics", "land_f40_atlas",
            "land_minwct_minus_true", "land_atlas2t_minus_true"]
    out = {k: [] for k in keys}
    land = None
    k40 = T_THR.index(-40)
    for mon, dd in all_days():
        z = np.load(f"{OUT}/daily/{mon}_{dd:02d}.npz")
        nh = int(z["n_hours"])
        mw = read_metrics(f"{MET}/daily_WCT_stats/{mon}_{dd:02d}_WCT_stats.nc", ["min_WCT"])["min_WCT"]
        m2 = read_metrics(f"{MET}/daily_2T_stats/{mon}_{dd:02d}_2T_stats.nc", ["frequency_-40"])["frequency_-40"]
        ms = read_metrics(f"{MET}/daily_WSPD_stats/{mon}_{dd:02d}_WSPD_stats.nc", ["max_WSPD"])["max_WSPD"]
        aw = read_atlas_tif(f"{ATLAS}/{mon}/Daily/{dd:02d}/WCT/Extreme/{mon}_{dd:02d}_WCT_min.tif")
        a2 = read_atlas_tif(f"{ATLAS}/{mon}/Daily/{dd:02d}/2T/Extreme/{mon}_{dd:02d}_2T_min.tif")
        af = read_atlas_tif(f"{ATLAS}/{mon}/Daily/{dd:02d}/2T/Frequency/{mon}_{dd:02d}_2T_freq_-40.tif")
        if land is None:
            land = np.isfinite(aw)
        t2true = k_to_f(z["T2_true_min"].astype(np.float64))
        out["fb_wct_true"].append(z["WCT_true_min"][i, j])
        out["fb_wct_meanann"].append(z["WCT_meanann_min"][i, j])
        out["fb_wct_p1"].append(z["WCT_p1"][i, j])
        out["fb_wct_metrics"].append(mw[i, j])
        out["fb_wct_atlas"].append(aw[i, j])
        out["fb_ws_true"].append(z["WS_true_max"][i, j])
        out["fb_ws_meanann"].append(z["WS_meanann_max"][i, j])
        out["fb_ws_metrics"].append(ms[i, j])
        out["fb_t2_true"].append(t2true[i, j])
        out["fb_t2_atlas"].append(a2[i, j])
        out["land_f40_raw"].append((z["T2F_count_le"][k40] / nh * 100)[land].mean())
        out["land_f40_metrics"].append(m2[land].mean())
        out["land_f40_atlas"].append(np.nanmean(af[land]))
        out["land_minwct_minus_true"].append((mw - z["WCT_true_min"])[land].mean())
        out["land_atlas2t_minus_true"].append(np.nanmean((a2 - t2true)[land]))
        print(mon, dd, flush=True)
    labels = np.array([f"{m} {d}" for m, d in all_days()])
    np.savez(f"{OUT}/misc/v9_figdata.npz", labels=labels, **{k: np.array(v, np.float64) for k, v in out.items()})


if __name__ == "__main__":
    main()
