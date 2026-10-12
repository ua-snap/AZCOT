"""V8: issue 10 — which temperature is WCT.nc built from, hour by hour, and what difference it makes.

(a) For every (day, year, hour) of the season: does WCT.nc match the NWS formula with SKT (max |diff| < 0.01 F over the grid),
    with 2T, or neither?  -> tables/v8_wct_source_by_hour.csv (one row per hour) and v8_wct_source_by_day.csv.
(b) Re-derive the doc's Jan 15 impact table and the same numbers for the whole season (non-glacier land, Atlas land mask),
    plus site values -> tables/v8_impact.csv.
"""
import os

import numpy as np
import pandas as pd

from common import ATLAS, OUT, SITES, all_days, cell, k_to_f, read_atlas_tif

HERE = os.path.dirname(os.path.abspath(__file__))
TAB = os.path.join(HERE, "..", "tables")
WCT_THR = list(range(0, -101, -5))


def main():
    rows = []
    for mon, dd in all_days():
        z = np.load(f"{OUT}/daily/{mon}_{dd:02d}.npz")
        ys = z["years"]
        s = z["hourly_wct_skt_maxabs"]
        t = z["hourly_wct_2t_maxabs"]
        for iy, y in enumerate(ys):
            for h in range(24):
                src = "SKT" if s[iy, h] < 0.01 else ("2T" if t[iy, h] < 0.01 else "neither")
                rows.append(dict(mon=mon, dd=dd, year=int(y), hour=h, skt_maxabs=s[iy, h], t2_maxabs=t[iy, h], source=src))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(TAB, "v8_wct_source_by_hour.csv"), index=False, float_format="%.6g")
    byday = df.groupby(["mon", "dd"], sort=False).source.value_counts().unstack(fill_value=0).reset_index()
    order = {m: i for i, m in enumerate(["oct", "nov", "dec", "jan", "feb", "mar"])}       # unstack sorts months A-Z
    byday = byday.assign(_o=byday["mon"].map(order)).sort_values(["_o", "dd"]).drop(columns="_o").reset_index(drop=True)
    byday.to_csv(os.path.join(TAB, "v8_wct_source_by_day.csv"), index=False)
    print("hours by source:", df.source.value_counts().to_dict())
    print("days with any 2T hour:", byday[byday.get("2T", 0) > 0][["mon", "dd"]].astype(str).agg(" ".join, axis=1).tolist())
    print("2T hours by year:", df[df.source == "2T"].groupby("year").size().to_dict())
    print("2T days all-2T? ", byday[byday.get("2T", 0) > 0].to_string())

    # (b) impact
    land = np.isfinite(read_atlas_tif(f"{ATLAS}/jan/Daily/15/WCT/Extreme/jan_15_WCT_min.tif"))
    sea = np.load(f"{OUT}/misc/v3_season.npz") if os.path.exists(f"{OUT}/misc/v3_season.npz") else None
    out = []

    def block(label, Z, nh, mask):
        k40, k65 = WCT_THR.index(-40), WCT_THR.index(-65)
        r = dict(period=label, n_cells=int(mask.sum()))
        r["mean_wct2t_minus_wct"] = float((-Z["sum_wct_minus_wct2t"][mask] / nh).mean())
        r["mean_2t_minus_skt"] = float((-Z["sum_skt_minus_2t"][mask] / nh).mean())
        dmin = Z["wct2t_min"] - Z["wct_min"]
        r["recordlow_diff_mean"] = float(dmin[mask].mean())
        r["recordlow_diff_p95"] = float(np.percentile(dmin[mask], 95))
        r["recordlow_diff_max"] = float(dmin[mask].max())
        r["recordlow_diff_share_colder_with_2t"] = float(np.mean(dmin[mask] < -1e-3))
        r["pct_le40_wct"] = float((Z["wct_c"][k40][mask] / nh * 100).mean())
        r["pct_le40_wct2t"] = float((Z["wct2t_c"][k40][mask] / nh * 100).mean())
        r["pct_le65_wct"] = float((Z["wct_c"][k65][mask] / nh * 100).mean())
        r["pct_le65_wct2t"] = float((Z["wct2t_c"][k65][mask] / nh * 100).mean())
        for name, (la, lo) in SITES.items():
            i, j = cell(la, lo)
            r[f"{name}_le40_wct"] = float(Z["wct_c"][k40][i, j] / nh * 100)
            r[f"{name}_le40_wct2t"] = float(Z["wct2t_c"][k40][i, j] / nh * 100)
            r[f"{name}_recordlow_wct"] = float(Z["wct_min"][i, j])
            r[f"{name}_recordlow_wct2t"] = float(Z["wct2t_min"][i, j])
        return r

    z = np.load(f"{OUT}/daily/jan_15.npz")
    Zj = dict(sum_wct_minus_wct2t=z["sum_wct_minus_wct2t"], sum_skt_minus_2t=z["sum_skt_minus_2t"],
              wct_min=z["WCT_true_min"], wct2t_min=z["WCT2T_true_min"], wct_c=z["WCT_count_le"], wct2t_c=z["WCT2T_count_le"])
    glacier_j = z["SL_true_min"] > 2000
    out.append(block("Jan 15, Atlas land", Zj, int(z["n_hours"]), land))
    out.append(block("Jan 15, Atlas land minus glacier", Zj, int(z["n_hours"]), land & ~glacier_j))
    if sea is not None:
        Zs = dict(sum_wct_minus_wct2t=sea["sum_wct_minus_wct2t"], sum_skt_minus_2t=sea["sum_skt_minus_2t"],
                  wct_min=sea["wct_true_min"], wct2t_min=sea["wct2t_true_min"], wct_c=sea["WCT_count_le"],
                  wct2t_c=sea["WCT2T_count_le"])
        glacier = sea["sl_min"] > 2000
        nh = int(sea["hours"])
        out.append(block("Oct-Mar, Atlas land", Zs, nh, land))
        out.append(block("Oct-Mar, Atlas land minus glacier", Zs, nh, land & ~glacier))
        # TR-26-5 headline: unweighted land-pixel mean of the daily frequency_-65, averaged over the 183 days
        out[-2]["tr_headline_metrics_daily_mean"] = float((sea["daily_freq65_metrics"][land] / 183).mean())
        out[-2]["tr_headline_rawSKTfile_daily_mean"] = float((sea["daily_freq65_skt"][land] / 183).mean())
        out[-2]["tr_headline_2T_daily_mean"] = float((sea["daily_freq65_2t"][land] / 183).mean())
    pd.DataFrame(out).T.to_csv(os.path.join(TAB, "v8_impact.csv"), header=[o["period"] for o in out])
    print(pd.DataFrame(out).T.to_string())


if __name__ == "__main__":
    main()
