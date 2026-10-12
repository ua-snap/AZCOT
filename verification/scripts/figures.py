"""Figures for VERIFICATION.md (run with the azcot-eda env: matplotlib + cartopy).

Reads only verification outputs (OUT/misc/*.npz, verification/tables/*.csv); writes verification/figures/*.png.
Palette: validated reference palette from the dataviz skill (categorical slots in fixed order; blue sequential;
blue<->red diverging with a gray midpoint).
"""
import os

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

OUT = "/import/beegfs/CMIP6/jdpaul3/azcot_verify"
HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "..", "figures")
TAB = os.path.join(HERE, "..", "tables")

S1, S2, S3, S4, S5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
SEQ = LinearSegmentedColormap.from_list("blue", ["#f0efec", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
DIV = LinearSegmentedColormap.from_list("div", ["#0d366b", "#3987e5", "#cde2fb", "#f0efec", "#f6c9c8", "#e34948", "#8f1f1f"])

mpl.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF, "font.family": "DejaVu Sans",
    "font.size": 9.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "legend.frameon": False, "lines.linewidth": 2.0,
})
MONTH_STARTS = [0, 31, 61, 92, 123, 152]
MONTH_NAMES = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
FEB29 = 151


def season_axis(ax, on_top=False):
    ax.set_xticks(MONTH_STARTS + [182], [f"{m} 1" for m in MONTH_NAMES] + ["Mar 31"])
    for m in MONTH_STARTS[1:]:
        ax.axvline(m - 0.5, color="white" if on_top else GRID, lw=0.8, zorder=5 if on_top else 0)
    ax.set_xlim(-1, 183)
    ax.grid(axis="x", visible=False)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def label_end(ax, x, y, text, color, dy=0):
    ax.annotate(text, (x, y), xytext=(4, dy), textcoords="offset points", color=INK2, fontsize=8.5, va="center")


def fig_minima(d):
    x = np.arange(183)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(x, d["fb_wct_true"], color=S1, label="True minimum of all hours (raw hourly files)")
    ax.plot(x, d["fb_wct_atlas"], color=S1, lw=0, marker="o", ms=2.6, alpha=0.9, label="Atlas WCT 'Minimum' raster")
    ax.plot(x, d["fb_wct_p1"], color=S3, lw=1.6, label="1st percentile (Metrics = raw)")
    ax.plot(x, d["fb_wct_meanann"], color=S2, lw=4.5, alpha=0.35, label="Mean of the 30 annual minima (raw)")
    ax.plot(x, d["fb_wct_metrics"], color=S2, lw=1.4, label="Metrics min_WCT")
    ax.annotate("Feb 29: min_WCT = sum of 8 yearly minima ÷ 30", (FEB29, d["fb_wct_metrics"][FEB29]), xytext=(-210, 18),
                textcoords="offset points", fontsize=8.5, color=INK2, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    season_axis(ax)
    ax.set_ylabel("Wind chill (°F)")
    ax.set_title("Issue 1–2: Metrics min_WCT is the mean of annual minima, not the record low (Fairbanks)")
    ax.legend(loc="upper center", fontsize=8, ncol=3, bbox_to_anchor=(0.5, -0.1))
    save(fig, "issue1_2_fairbanks_min_wct.png")


def fig_wind(d):
    x = np.arange(183)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(x, d["fb_ws_true"], color=S1, label="True maximum of all hours (raw)")
    ax.plot(x, d["fb_ws_meanann"], color=S2, lw=4.5, alpha=0.35, label="Mean of the 30 annual maxima (raw)")
    ax.plot(x, d["fb_ws_metrics"], color=S2, lw=1.4, label="Metrics max_WSPD (= min_WS10)")
    season_axis(ax)
    ax.set_ylabel("10 m wind (knots)")
    ax.set_ylim(0, None)
    ax.set_title("Issue 4: max_WSPD (and its duplicate min_WS10) is the mean of annual maxima (Fairbanks)")
    ax.legend(loc="upper left", fontsize=8, ncol=3)
    save(fig, "issue4_fairbanks_max_wspd.png")


def fig_2t_freq(d):
    x = np.arange(183)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(x, d["land_f40_raw"], color=S1, label="Raw hourly 2T (°F)")
    ax.plot(x, d["land_f40_atlas"], color=S3, lw=0, marker="o", ms=2.4, label="Atlas daily 2T frequency raster")
    ax.plot(x, d["land_f40_metrics"], color=S2, label="Metrics daily_2T_stats frequency_-40")
    season_axis(ax)
    ax.set_ylabel("% of hours ≤ −40 °F (land mean)")
    ax.set_title("Issue 3: Metrics daily 2T frequencies are 0 everywhere; the Atlas maps are correct")
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "issue3_2t_frequency.png")


def fig_sd_missing():
    f = pd.read_csv(os.path.join(TAB, "v5_sd_files.csv"))
    days = [(m, dd) for m, n in zip(["oct", "nov", "dec", "jan", "feb", "mar"], [31, 30, 31, 31, 29, 31]) for dd in range(1, n + 1)]
    idx = {k: i for i, k in enumerate(days)}
    grid = np.zeros((24, 183))
    for (m, dd, h), g in f.groupby(["mon", "dd", "hour"]):
        grid[h, idx[(m, dd)]] = len(g)
    fig, ax = plt.subplots(figsize=(9, 3.4))
    im = ax.imshow(np.where(grid > 0, grid, np.nan), aspect="auto", cmap=SEQ, vmin=0, vmax=30, origin="lower",
                   extent=(-0.5, 182.5, -0.5, 23.5), interpolation="nearest")
    season_axis(ax)
    ax.grid(False)
    ax.set_ylabel("UTC hour")
    ax.set_yticks([0, 6, 12, 18, 23])
    cb = fig.colorbar(im, ax=ax, pad=0.01)
    cb.set_label("years with an all-NaN file", color=INK2)
    ax.set_title("Issue 5: all-NaN snow-depth files — hours 01–23 of every month's last day")
    save(fig, "issue5_sd_missing_hours.png")


def fig_sd_bias():
    z = np.load(f"{OUT}/misc/v5_sd_monthly.npz")
    land = z["land"]
    ms = ["oct", "nov", "dec", "jan", "feb", "mar"]
    met = [z[f"{m}_met"][land].mean() for m in ms]
    fix = [z[f"{m}_fix"][land].mean() for m in ms]
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    x = np.arange(6)
    ax.bar(x - 0.19, met, 0.36, color=S2, label="Metrics (missing hours count as 'below', ÷720)")
    ax.bar(x + 0.19, fix, 0.36, color=S1, label="Divided by hours actually present")
    for xi, a, b in zip(x, met, fix):
        ax.text(xi, max(a, b) + 1.5, f"−{b - a:.1f}" if b - a >= 0.05 else "0.0", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(x, MONTH_NAMES)
    ax.set_ylim(0, 112)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("% of hours with snow depth ≥ 8 in\n(land mean of daily values)")
    ax.set_title("Issue 6: monthly SD frequency bias (pp)")
    ax.legend(loc="upper center", fontsize=8, bbox_to_anchor=(0.5, -0.1), ncol=1)
    save(fig, "issue6_sd_monthly_bias.png")


def fig_atlas2t(d):
    t = pd.read_csv(os.path.join(TAB, "v3_issue7.csv"))
    grid = np.zeros((24, 183))
    for k, s in enumerate(t["atlas2T_hours_below"].fillna("")):
        for h in str(s).split():
            grid[int(h), k] = 1
    fig, axs = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True, gridspec_kw=dict(height_ratios=[1.5, 1]))
    ax = axs[0]
    ax.imshow(np.where(grid > 0, 1, np.nan), aspect="auto", cmap=LinearSegmentedColormap.from_list("one", [S2, S2]),
              origin="lower", extent=(-0.5, 182.5, -0.5, 23.5), interpolation="nearest")
    ax.grid(False)
    ax.set_ylabel("UTC hour")
    ax.set_yticks([0, 6, 12, 18, 23])
    ax.set_title("Issue 7: hours that were left out of the Atlas daily 2T 'Lowest recorded' raster (orange)")
    season_axis(ax)
    ax = axs[1]
    ax.plot(np.arange(183), 100 * t["atlas2T_warmer"], color=S2)
    ax.set_ylabel("% of land cells where\nAtlas is warmer")
    ax.set_ylim(0, 100)
    season_axis(ax)
    save(fig, "issue7_atlas_2t_hours.png")


def fig_wct_source():
    b = pd.read_csv(os.path.join(TAB, "v8_wct_source_by_day.csv"))
    morder = {m: i for i, m in enumerate(["oct", "nov", "dec", "jan", "feb", "mar"])}
    b = b.assign(_o=b["mon"].map(morder)).sort_values(["_o", "dd"]).reset_index(drop=True)   # unstack sorted months A-Z
    assert len(b) == 183 and b.loc[61, "mon"] == "dec" and b.loc[61, "dd"] == 1
    tot = b[[c for c in ("SKT", "2T", "neither") if c in b]].sum(axis=1)
    fig, ax = plt.subplots(figsize=(9, 2.8))
    x = np.arange(183)
    ax.bar(x, 100 * b["SKT"] / tot, 1.0, color=S1, label="WCT.nc = NWS formula with skin temperature (SKT)")
    ax.bar(x, 100 * b["2T"] / tot, 1.0, bottom=100 * b["SKT"] / tot, color=S2, label="WCT.nc = NWS formula with 2 m air temperature (2T)")
    season_axis(ax, on_top=True)
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of the day's hours")
    ax.annotate("Dec 1–9: 2T, all 30 years", (65, 100), xytext=(75, 108), textcoords="data", fontsize=8.5, color=INK2,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8), annotation_clip=False)
    ax.annotate("Nov 2: 2T in 2000–2004", (32, 100), xytext=(8, 108), textcoords="data", fontsize=8.5, color=INK2,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8), annotation_clip=False)
    ax.set_title("Issue 10: which temperature each hourly WCT.nc file was built from (all 131,232 hours)", pad=24)
    ax.legend(loc="lower left", fontsize=8, ncol=2, bbox_to_anchor=(0, -0.42))
    save(fig, "issue10_wct_source_by_day.png")


def polar_map(ax, field, cells, cmap, norm, title):
    ax.set_extent([-180, 180, 60, 90], ccrs.PlateCarree())
    lat = 60 + 0.25 * np.arange(121)
    lon = -180 + 0.25 * np.arange(1440)
    f = np.where(cells, field, np.nan)
    m = ax.pcolormesh(lon, lat, f, cmap=cmap, norm=norm, transform=ccrs.PlateCarree(), shading="nearest", rasterized=True)
    ax.add_feature(cfeature.COASTLINE.with_scale("110m"), lw=0.4, edgecolor=INK2)
    ax.set_title(title, fontsize=9.5)
    return m


def fig_inversion_maps():
    v = np.load(f"{OUT}/misc/v7_fields.npz")
    cells = v["cells"]
    fig = plt.figure(figsize=(10, 4.6))
    proj = ccrs.NorthPolarStereo()
    ax1 = fig.add_subplot(1, 2, 1, projection=proj)
    m1 = polar_map(ax1, v["dT"], cells, DIV, TwoSlopeNorm(0, -10, 10), "Mean (SKT − 2T), Oct–Mar (°F)\nblue = skin colder than air")
    fig.colorbar(m1, ax=ax1, shrink=0.75, pad=0.03)
    ax2 = fig.add_subplot(1, 2, 2, projection=proj)
    m2 = polar_map(ax2, v["d40"], cells, DIV, TwoSlopeNorm(0, -10, 10),
                   "Extra % of hours with WCT ≤ −40 °F\n(AZCOT WCT.nc minus WCT from 2T)")
    m2.set_cmap(DIV.reversed())
    fig.colorbar(m2, ax=ax2, shrink=0.75, pad=0.03)
    fig.suptitle("Issue 10: skin-vs-air temperature difference and its effect on wind chill (non-glacier land)",
                 x=0.02, y=0.98, ha="left", fontweight="bold", color=INK, fontsize=10.5)
    fig.subplots_adjust(top=0.86, wspace=0.15)
    save(fig, "issue10_inversion_maps.png")


def fig_inversion_bins():
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.6), sharey=True)
    for ax, (fn, lab) in zip(axs, (("v7_by_dist_bin.csv", "Distance to coast (km)"), ("v7_by_lat_bin.csv", "Latitude (°N)"),
                                   ("v7_by_wind_bin.csv", "Mean 10 m wind (quintile)"))):
        t = pd.read_csv(os.path.join(TAB, fn))
        names = t.iloc[:, 0].astype(str).str.replace(" 20%", "\n20%").str.replace("-", "–\n", regex=False) \
            if "dist" in fn else t.iloc[:, 0].astype(str).str.replace(" 20%", "\n20%")
        ax.bar(np.arange(len(t)), t["dT"], 0.65, color=S1)
        for k, (val, n) in enumerate(zip(t["dT"], t["n"])):
            ax.text(k, val - 0.25, f"{val:.1f}", ha="center", va="top", fontsize=8, color=INK2)
        ax.set_xticks(np.arange(len(t)), names, fontsize=8)
        ax.set_xlabel(lab)
        ax.grid(axis="x", visible=False)
        ax.axhline(0, color=AXIS, lw=0.8)
    axs[0].set_ylabel("Mean (SKT − 2T), °F\n(more negative = stronger inversion)")
    fig.suptitle("Issue 10: skin-minus-air temperature by distance to coast, latitude and wind (non-glacier land, Oct–Mar)",
                 x=0.02, ha="left", fontweight="bold", color=INK, fontsize=10.5)
    save(fig, "issue10_inversion_by_distance_lat_wind.png")


def fig_lat_dist():
    t = pd.read_csv(os.path.join(TAB, "v7_dT_lat_x_dist.csv"), index_col=0)
    n = pd.read_csv(os.path.join(TAB, "v7_n_lat_x_dist.csv"), index_col=0)
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    im = ax.imshow(t.values, cmap=SEQ.reversed(), vmin=-12, vmax=0, aspect="auto")
    ax.grid(False)
    for (i, j), val in np.ndenumerate(t.values):
        if np.isfinite(val):
            ax.text(j, i, f"{val:.1f}\n(n={int(n.values[i, j])})", ha="center", va="center", fontsize=7.5,
                    color="white" if val < -6 else INK)
    ax.set_xticks(range(t.shape[1]), [c + " km" for c in t.columns], fontsize=8)
    ax.set_yticks(range(t.shape[0]), [r + "°N" for r in t.index], fontsize=8)
    ax.set_xlabel("Distance to coast")
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("mean (SKT − 2T), °F", color=INK2)
    ax.set_title("Issue 10: within a latitude band, coastal cells are not the strongest")
    save(fig, "issue10_lat_x_distance.png")


def main():
    os.makedirs(FIG, exist_ok=True)
    d = dict(np.load(f"{OUT}/misc/v9_figdata.npz"))
    fig_minima(d)
    fig_wind(d)
    fig_2t_freq(d)
    fig_sd_missing()
    fig_sd_bias()
    if os.path.exists(os.path.join(TAB, "v3_issue7.csv")):
        fig_atlas2t(d)
    fig_wct_source()
    if os.path.exists(f"{OUT}/misc/v7_fields.npz"):
        fig_inversion_maps()
        fig_inversion_bins()
        fig_lat_dist()


if __name__ == "__main__":
    main()
