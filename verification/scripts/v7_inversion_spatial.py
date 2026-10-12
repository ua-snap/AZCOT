"""V7: where is the skin-vs-air temperature effect on wind chill largest?  Tests the issue-10 sentence
"The effect is largest where strong inversions form (high Arctic, coasts)".

Season (Oct-Mar, all 131,232 hours) per-cell quantities from v3_season.npz:
  dT      = mean(SKT - 2T) [F]; negative = skin colder than air (surface-based inversion)
  dT_calm = mean(SKT - 2T) over hours with 10 m wind < 5 kn
  d40     = (% hours WCT_SKTfile <= -40) - (% hours WCT_2T <= -40)  [pp]  (the effect on a threshold frequency)
  d65     = same at -65 F
  wind    = mean 10 m wind [kn]; calm = share of hours < 5 kn
Covariates: distance to the nearest non-land grid cell (Atlas land mask; great-circle km), ERA5 orography (m), latitude.
Cells: Atlas land mask minus glacier-cap cells (SL >= 2000 lb/ft2 in every hour). Unweighted cell statistics.
Writes tables/v7_*.csv and OUT/misc/v7_fields.npz (for figures).
"""
import os

import netCDF4
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from common import AKCASC, LAT, LON, OUT

HERE = os.path.dirname(os.path.abspath(__file__))
TAB = os.path.join(HERE, "..", "tables")
THR = list(range(0, -101, -5))
R_EARTH = 6371.0


def xyz(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]


def main():
    s = np.load(f"{OUT}/misc/v3_season.npz")
    nh = float(s["hours"])
    land = s["land"]
    glacier = s["sl_min"] >= 2000
    cells = land & ~glacier
    LA, LO = np.meshgrid(LAT, LON, indexing="ij")

    # distance to nearest non-land cell in the grid
    tree = cKDTree(xyz(LA[~land], LO[~land]))
    chord, _ = tree.query(xyz(LA.ravel(), LO.ravel()))
    dist = (2 * R_EARTH * np.arcsin(np.clip(chord / 2, 0, 1))).reshape(LA.shape)
    dist[~land] = 0.0
    # distance to the grid's southern edge (60N): nearest ocean could lie south of the grid, so flag lower bounds
    to_edge = (LA - 59.875) * 111.2
    lower_bound = dist > to_edge

    # orography
    with netCDF4.Dataset(f"{AKCASC.replace('reanalysis-era5-single-levels', 'reanalysis-era5-invariants')}/era5_geopotential.nc") as ds:
        z = np.asarray(ds["z"][0, :121, :], np.float64) / 9.80665
        assert np.allclose(ds["latitude"][:121], 90 - 0.25 * np.arange(121))
    elev = np.roll(z, -720, axis=1)[::-1, :]

    k40, k65 = THR.index(-40), THR.index(-65)
    f = dict(
        dT=s["sum_skt_minus_2t"] / nh,
        dT_calm=np.where(s["n_calm"] > 0, s["sum_skt_minus_2t_calm"] / np.maximum(s["n_calm"], 1), np.nan),
        d40=(s["WCT_count_le"][k40] - s["WCT2T_count_le"][k40]) / nh * 100,
        d65=(s["WCT_count_le"][k65] - s["WCT2T_count_le"][k65]) / nh * 100,
        dmin=s["wct_true_min"] - s["wct2t_true_min"],
        wind=s["sum_ws"] / nh,
        calm=s["n_calm"] / nh * 100,
        dist=dist, elev=elev, lat=LA, lower_bound=lower_bound,
    )
    np.savez(f"{OUT}/misc/v7_fields.npz", land=land, glacier=glacier, cells=cells, **f)

    df = pd.DataFrame({k: v[cells] for k, v in f.items()})
    df["dist_bin"] = pd.cut(df.dist, [0, 1, 50, 100, 200, 400, 800, 5000], right=False,
                            labels=["coast cell (adjacent)", "1-50", "50-100", "100-200", "200-400", "400-800", ">800"])
    df["lat_bin"] = pd.cut(df.lat, [60, 65, 70, 75, 80, 90.1], right=False, labels=["60-65", "65-70", "70-75", "75-80", "80-90"])
    df["elev_bin"] = pd.cut(df.elev, [-500, 200, 500, 1000, 2000, 9000], labels=["<200", "200-500", "500-1000", "1000-2000", ">2000"])
    df["wind_bin"] = pd.qcut(df.wind, 5, labels=["calmest 20%", "q2", "q3", "q4", "windiest 20%"])
    agg = dict(n=("dT", "size"), dT=("dT", "mean"), dT_calm=("dT_calm", "mean"), d40=("d40", "mean"), d65=("d65", "mean"),
               dmin=("dmin", "mean"), wind=("wind", "mean"), calm=("calm", "mean"), elev=("elev", "median"),
               dist=("dist", "median"), lat=("lat", "mean"))
    out = {}
    for b in ("dist_bin", "lat_bin", "elev_bin", "wind_bin"):
        out[b] = df.groupby(b, observed=True).agg(**agg)
        out[b].to_csv(os.path.join(TAB, f"v7_by_{b}.csv"), float_format="%.4g")
    # distance effect within latitude bands (separates 'coast' from 'high Arctic')
    piv = df.pivot_table(index="lat_bin", columns="dist_bin", values="dT", aggfunc="mean", observed=True)
    pivn = df.pivot_table(index="lat_bin", columns="dist_bin", values="dT", aggfunc="size", observed=True)
    piv.to_csv(os.path.join(TAB, "v7_dT_lat_x_dist.csv"), float_format="%.3g")
    pivn.to_csv(os.path.join(TAB, "v7_n_lat_x_dist.csv"))
    piv40 = df.pivot_table(index="lat_bin", columns="dist_bin", values="d40", aggfunc="mean", observed=True)
    piv40.to_csv(os.path.join(TAB, "v7_d40_lat_x_dist.csv"), float_format="%.3g")
    # where are the strongest effects? top decile of cells by inversion strength (most negative dT) and by d40
    top = {}
    for col, asc in (("dT", True), ("d40", False), ("d65", False)):
        q = df[col].quantile(0.1 if asc else 0.9)
        sel = df[df[col] <= q] if asc else df[df[col] >= q]
        top[col] = dict(n=len(sel), median_dist_km=sel.dist.median(), share_within_50km=(sel.dist < 50).mean(),
                        share_over_200km=(sel.dist >= 200).mean(), median_elev=sel.elev.median(), mean_lat=sel.lat.mean(),
                        mean_wind=sel.wind.mean())
    top["all cells"] = dict(n=len(df), median_dist_km=df.dist.median(), share_within_50km=(df.dist < 50).mean(),
                            share_over_200km=(df.dist >= 200).mean(), median_elev=df.elev.median(), mean_lat=df.lat.mean(),
                            mean_wind=df.wind.mean())
    topdf = pd.DataFrame(top).T
    topdf.to_csv(os.path.join(TAB, "v7_top_decile.csv"), float_format="%.4g")
    cor = df[["dT", "dT_calm", "d40", "dist", "elev", "lat", "wind", "calm"]].corr(method="spearman")
    cor.to_csv(os.path.join(TAB, "v7_spearman.csv"), float_format="%.3f")
    # sensitivity: drop cells whose coast distance is only a lower bound (nearest ocean may be south of 60N)
    sens = df[~df.lower_bound.astype(bool)].groupby("dist_bin", observed=True).agg(**agg)
    sens.to_csv(os.path.join(TAB, "v7_by_dist_bin_excl_lowerbound.csv"), float_format="%.4g")
    pd.set_option("display.width", 220)
    for k, v in out.items():
        print("=====", k); print(v.round(3).to_string())
    print("===== dT lat x dist"); print(piv.round(2).to_string()); print(pivn.to_string())
    print("===== d40 lat x dist"); print(piv40.round(2).to_string())
    print("===== top decile"); print(topdf.round(3).to_string())
    print("===== spearman"); print(cor.round(2).to_string())
    print("===== dist bins excluding lower-bound cells"); print(sens.round(3).to_string())


if __name__ == "__main__":
    main()


def controlled():
    """Does distance to the coast matter once latitude, elevation and wind are held fixed?
    Standardized OLS of dT on (lat, elev, log wind, log distance), with and without perennial-snow cells
    (season minimum SL >= 50 lb/ft2: partly glaciated cells that never lose their snow)."""
    v = np.load(f"{OUT}/misc/v7_fields.npz")
    s = np.load(f"{OUT}/misc/v3_season.npz")
    rows = []
    for label, cells in (("non-glacier land", v["cells"]), ("non-glacier land, no perennial snow", v["cells"] & (s["sl_min"] < 50))):
        X = np.c_[v["lat"][cells], v["elev"][cells], np.log(v["wind"][cells]), np.log(v["dist"][cells])]
        y = v["dT"][cells]
        Xs = (X - X.mean(0)) / X.std(0)
        A = np.c_[np.ones(len(y)), Xs]
        beta, *_ = np.linalg.lstsq(A, (y - y.mean()) / y.std(), rcond=None)
        res = y - A @ (beta * y.std()) - y.mean()
        r2 = 1 - res.var() / y.var()
        # partial rank correlation of distance with dT, controlling the other three
        rk = lambda a: pd.Series(a).rank().to_numpy()
        Z = np.c_[np.ones(len(y)), rk(X[:, 0]), rk(X[:, 1]), rk(X[:, 2])]
        ry = rk(y) - Z @ np.linalg.lstsq(Z, rk(y), rcond=None)[0]
        rd = rk(X[:, 3]) - Z @ np.linalg.lstsq(Z, rk(X[:, 3]), rcond=None)[0]
        rows.append(dict(cells=label, n=int(cells.sum()), beta_lat=beta[1], beta_elev=beta[2], beta_logwind=beta[3],
                         beta_logdist=beta[4], r2=r2, partial_spearman_dist=np.corrcoef(ry, rd)[0, 1]))
        if "perennial" in label:
            df = pd.DataFrame(dict(dT=y, lat=X[:, 0], dist=v["dist"][cells]))
            df["lat_bin"] = pd.cut(df.lat, [60, 65, 70, 75, 80, 90.1], right=False)
            df["dist_bin"] = pd.cut(df.dist, [0, 50, 100, 200, 400, 800, 5000], right=False)
            p = df.pivot_table(index="lat_bin", columns="dist_bin", values="dT", aggfunc="mean", observed=True)
            p.to_csv(os.path.join(TAB, "v7_dT_lat_x_dist_no_perennial.csv"), float_format="%.3g")
            print("dT lat x dist, no perennial snow:"); print(p.round(2).to_string())
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(TAB, "v7_controlled.csv"), index=False, float_format="%.4g")
    print("(betas: standardized; negative beta = stronger skin-colder-than-air signal as the covariate increases)")
    print(out.round(3).to_string())


if __name__ == "__main__" and os.environ.get("V7_CONTROLLED"):
    controlled()
