"""Make the EDA figures (eda/figures/*.png) from the cached daily cubes.

Run build_cubes.py first. Usage: python figures.py [fig_name ...]
"""
import sys

import cartopy.crs as ccrs
import matplotlib

matplotlib.use("Agg")
import matplotlib.path as mpath
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap

from azcot import FIGS, LOCATIONS, load_cube, load_masks, nearest_land_cell

# ---- style (reference palette from the dataviz skill) ----------------------------------
SURFACE, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
        "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]  # steps 100..700
ORANGE = ["#fdeee6", "#f9cdb7", "#f4a988", "#eb6834", "#c4501f", "#963a13", "#6b280b"]
GLACIER = "#c9c8c2"
NEVER = "#f0efec"
BLUE_SEQ = LinearSegmentedColormap.from_list("blue_seq", BLUE)
ORANGE_SEQ = LinearSegmentedColormap.from_list("orange_seq", ORANGE)
MONTH_NAMES = ["October", "November", "December", "January", "February", "March"]
MONTH_KEYS = ["oct", "nov", "dec", "jan", "feb", "mar"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 9, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": BASE, "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlesize": 10,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
})
PROJ = ccrs.NorthPolarStereo(central_longitude=-100)


def polar_axes(fig, nrows, ncols, idx):
    ax = fig.add_subplot(nrows, ncols, idx, projection=PROJ)
    ax.set_extent([-180, 180, 60, 90], ccrs.PlateCarree())
    theta = np.linspace(0, 2 * np.pi, 200)
    circle = mpath.Path(np.vstack([np.sin(theta), np.cos(theta)]).T * 0.5 + 0.5)
    ax.set_boundary(circle, transform=ax.transAxes)
    ax.coastlines("50m", linewidth=0.4, color=INK2)
    ax.gridlines(color=GRID, linewidth=0.4, xlocs=range(-180, 180, 30), ylocs=[60, 70, 80])
    return ax


def draw(ax, da, **kw):
    # Wrap the dateline by hand: float32 lons fail cartopy's equal-spacing check.
    lon = np.append(da.g0_lon_1.values.astype(float), float(da.g0_lon_1[0]) + 360)
    data = np.concatenate([da.values, da.values[..., :1]], axis=-1)
    return ax.pcolormesh(lon, da.g0_lat_0.values, data, transform=ccrs.PlateCarree(),
                         shading="nearest", rasterized=True, **kw)


def draw_classes(ax, da, bounds, colors):
    """Draw da binned by `bounds` (len(colors)+1 edges) as ordinal classes 0..n-1."""
    idx = xr.apply_ufunc(lambda v: np.where(np.isnan(v), np.nan, np.digitize(v, bounds[1:-1])), da)
    n = len(colors)
    return draw(ax, idx, cmap=ListedColormap(colors), norm=BoundaryNorm(np.arange(-0.5, n), n))


def class_colorbar(fig, mappable, axes, label, ticklabels):
    cb = colorbar(fig, mappable, axes, label)
    cb.set_ticks(range(len(ticklabels)))
    cb.set_ticklabels(ticklabels, fontsize=7)
    cb.ax.tick_params(length=0)
    return cb


def draw_glacier(ax, masks):
    g = masks.glacier.where(masks.glacier)
    draw(ax, g, cmap=ListedColormap([GLACIER]), vmin=0, vmax=1)


def save(fig, name, note=None):
    if note:
        fig.text(0.01, 0.005, note, fontsize=7, color=MUTED, ha="left", va="bottom")
    FIGS.mkdir(exist_ok=True)
    fig.savefig(FIGS / f"{name}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name, flush=True)


def monthly(da, how="mean"):
    month = xr.DataArray([d.split("_")[0] for d in da.day.values], dims="day")
    return getattr(da.groupby(month.rename("month")), how)("day")


def colorbar(fig, mappable, axes, label, **kw):
    cb = fig.colorbar(mappable, ax=axes, orientation="horizontal", fraction=0.04, pad=0.03, aspect=40, **kw)
    cb.set_label(label, color=INK2)
    cb.outline.set_visible(False)
    if isinstance(mappable.norm, BoundaryNorm) and not np.allclose(np.diff(mappable.norm.boundaries), 1):
        cb.set_ticks(mappable.norm.boundaries)
        cb.ax.xaxis.set_major_formatter("{x:g}")
    return cb


def six_month_maps(name, da, title, label, cmap, norm, masks=None, note=None, extend="neither"):
    fig = plt.figure(figsize=(11, 8))
    axes = []
    for i, (key, mname) in enumerate(zip(MONTH_KEYS, MONTH_NAMES)):
        ax = polar_axes(fig, 2, 3, i + 1)
        m = draw(ax, da.sel(month=key), cmap=cmap, norm=norm)
        if masks is not None:
            draw_glacier(ax, masks)
        ax.set_title(mname, fontsize=9)
        axes.append(ax)
    fig.suptitle(title, fontsize=12, fontweight="bold", x=0.02, ha="left")
    colorbar(fig, m, axes, label, extend=extend)
    save(fig, name, note)


# ---- point helpers -----------------------------------------------------------------------
def point_series(cube, masks):
    out = {}
    for name, lat, lon in LOCATIONS:
        i, j = nearest_land_cell(lat, lon, masks.land)
        out[name] = cube.isel(g0_lat_0=i, g0_lon_1=j)
    return out


def threshold_line(ax, y, text):
    ax.axhline(y, color=MUTED, lw=0.8, ls=(0, (4, 3)), zorder=1)
    ax.text(1.0, y, f" {text}", transform=ax.get_yaxis_transform(), va="center", ha="left",
            fontsize=7, color=MUTED, clip_on=False)


def month_axis(ax, dates):
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_xlim(dates[0], dates[-1])


# ---- WCT figures -------------------------------------------------------------------------
def fig_wct_monthly_mean(wct, masks):
    da = monthly(wct.averageTemp)
    levels = np.arange(-70, 31, 10)
    six_month_maps("wct_monthly_mean", da, "Average wind chill by month, 1991–2020",
                   "Average wind chill temperature (°F) — mean of every hour in the month across 30 winters",
                   BLUE_SEQ.reversed(), BoundaryNorm(levels, 256, extend="both"), extend="both",
                   note="Source: disk1/Metrics/daily_WCT_stats, averageTemp averaged over the days of each month.")


def fig_wct_freq_m40(wct, masks):
    da = monthly(wct["frequency_-40"])
    levels = [0, 1, 5, 10, 20, 30, 40, 50, 60, 80, 100]
    six_month_maps("wct_freq_le_m40_monthly", da,
                   "How often wind chill is at or below −40 °F (frostbite in under 10 minutes)",
                   "Share of hours with wind chill ≤ −40 °F (%), 1991–2020",
                   BLUE_SEQ, BoundaryNorm(levels, 256),
                   note="frequency_-40 = % of the 720 hours (30 yr × 24 h) per calendar day with WCT ≤ −40 °F; "
                        "averaged over the days of each month.")


def fig_wct_freq_m65_season(wct, masks):
    season = wct["frequency_-65"].mean("day")
    peak = monthly(wct["frequency_-65"]).max("month")
    levels = [0, 0.1, 1, 2, 5, 10, 20, 30, 50, 75]
    fig = plt.figure(figsize=(10, 5.6))
    axes = []
    for k, (da, t) in enumerate([(season, "Whole season (Oct–Mar)"), (peak, "Worst month")]):
        ax = polar_axes(fig, 1, 2, k + 1)
        m = draw(ax, da, cmap=BLUE_SEQ, norm=BoundaryNorm(levels, 256))
        ax.set_title(t, fontsize=9)
        axes.append(ax)
    fig.suptitle("Where the Army's −65 °F requirement actually bites: share of hours with wind chill ≤ −65 °F",
                 fontsize=11, fontweight="bold", x=0.02, ha="left")
    colorbar(fig, m, axes, "Share of hours (%), 1991–2020")
    save(fig, "wct_freq_le_m65_season",
         "Left: frequency_-65 averaged over all 183 days. Right: highest monthly average.")


def fig_wct_zones(wct, masks):
    jan = wct.sel(day=[d for d in wct.day.values if d.startswith("jan")])
    panels = [(jan.averageTemp.mean("day"), "Typical January hour (average)"),
              (jan.percentile_1.mean("day"), "Cold extreme: January 1st-percentile hour")]
    bounds = [-200, -61, -51, -41, -25, -5, 20, 200]
    labels = ["5C\n< −61", "5B\n−51…−60", "5A\n−41…−50", "4\n−25…−40", "3\n−5…−24", "2\n19…−4", "1 or milder\n≥ 20"]
    fig = plt.figure(figsize=(10.5, 6))
    axes = []
    for k, (da, t) in enumerate(panels):
        ax = polar_axes(fig, 1, 2, k + 1)
        m = draw_classes(ax, da.where(masks.land), bounds, BLUE[12:5:-1])
        ax.set_title(t, fontsize=9)
        axes.append(ax)
    class_colorbar(fig, m, axes, "ATP 3-90.96 cold zone, applied to wind chill (°F)", labels)
    fig.suptitle("Which cold zone to equip for in January? Typical vs. 1-in-100-hour wind chill (land)",
                 fontsize=12, fontweight="bold", x=0.02, ha="left")
    save(fig, "wct_cold_zones",
         "Left: January mean of averageTemp. Right: January mean of percentile_1 (colder than all but 1% of each "
         "day's 720 hours). Zones from TR-26-5 Table 2.")


def fig_wct_points(wct, masks):
    pts = point_series(wct, masks)
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.2), sharex=True, sharey=True)
    for ax, (name, s) in zip(axes.flat, pts.items()):
        d = s.date.values
        ax.fill_between(d, s.percentile_1, s.percentile_50, color=BLUE[3], alpha=0.45, lw=0,
                        label="1st–50th percentile hour")
        ax.plot(d, s.averageTemp, color=BLUE[9], lw=2, label="Average")
        ax.plot(d, s.min_WCT, color=BLUE[12], lw=1.2, ls=(0, (1, 1.5)), label="min_WCT (avg of yearly lows)")
        threshold_line(ax, -40, "−40")
        threshold_line(ax, -65, "−65")
        ax.set_title(name, fontsize=9, loc="left")
        month_axis(ax, d)
    axes[0, 0].set_ylabel("Wind chill (°F)")
    axes[1, 0].set_ylabel("Wind chill (°F)")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=3, fontsize=8, bbox_to_anchor=(0.99, 1.0))
    fig.suptitle("Wind chill through the cold season at eight locations", fontsize=12, fontweight="bold",
                 x=0.01, ha="left", y=1.0)
    fig.tight_layout(rect=(0, 0.02, 0.97, 0.95))
    save(fig, "wct_points_seasonal", "Nearest land grid cell. Daily 30-year climatology. The min_WCT spike at Mar 1 is the Feb 29 bug (sum of 8 yearly lows ÷ 30); "
                                     "dashed reference lines at −40 °F and −65 °F.")


def fig_wct_min_caveat():
    # Fairbanks grid cell (64.75N, 147.75W), Jan 15. Values recomputed from the 720 raw hourly WCT files
    # (see .claude notes / EDA.md); kept here so the figure is reproducible without re-reading raw data.
    rows = [("Record hourly low (true minimum)", -62.66), ("percentile_1", -59.34),
            ("min_WCT (as stored)", -18.70), ("percentile_50", -10.50), ("averageTemp", -12.03)]
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    y = np.arange(len(rows))
    for k, (lab, v) in enumerate(rows):
        hi = lab.startswith("min_WCT") or lab.startswith("Record")
        ax.plot(v, k, "o", ms=8, color=BLUE[9] if hi else BLUE[4], mec=SURFACE, mew=2)
        ax.text(v - 1.5, k, f"{v:.1f}", ha="right", va="center", fontsize=8, color=INK)
    ax.set_yticks(y, [r[0] for r in rows])
    ax.set_xlim(-70, -5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Wind chill (°F), Fairbanks grid cell, January 15")
    ax.set_title("min_WCT is not the record low: it averages the 30 yearly lows", loc="left")
    fig.subplots_adjust(bottom=0.28)
    save(fig, "wct_min_caveat", "Recomputed from the 720 hourly files in disk1/data/jan/15 (30 years × 24 hours).")


def fig_wct_consecutive(wct, masks):
    da = monthly(wct["consecutive_-40"]).sel(month="jan")
    fr = monthly(wct["frequency_-40"]).sel(month="jan")
    fig = plt.figure(figsize=(10, 5.6))
    ax1 = polar_axes(fig, 1, 2, 1)
    m1 = draw(ax1, fr, cmap=BLUE_SEQ, norm=BoundaryNorm([0, 1, 5, 10, 20, 30, 40, 50, 60, 80, 100], 256))
    ax1.set_title("How often: % of January hours ≤ −40 °F", fontsize=9)
    ax2 = polar_axes(fig, 1, 2, 2)
    m2 = draw(ax2, da, cmap=BLUE_SEQ, norm=BoundaryNorm([0, 1, 2, 4, 6, 8, 12, 16, 20, 24], 256))
    ax2.set_title("consecutive_-40: mean spell hours/day (no-spell years = 0)", fontsize=9)
    colorbar(fig, m1, [ax1], "%")
    colorbar(fig, m2, [ax2], "hours (max 24)")
    fig.suptitle("January: how often vs. the stored persistence metric for −40 °F wind chill", fontsize=12, fontweight="bold",
                 x=0.02, ha="left")
    save(fig, "wct_jan_freq_vs_duration",
         "consecutive_-40: for each day/year, mean length of runs with WCT ≤ −40 °F within that day's 24 h "
         "(0 if none), averaged over 30 years, so it mixes how often spells occur with how long they last. "
         "Spells are cut at midnight UTC.")


# ---- SL figures --------------------------------------------------------------------------
def sl_land(da, masks):
    return da.where(masks.land & ~masks.glacier)


def fig_sl_monthly_mean(sl, masks):
    da = sl_land(monthly(sl.averageSL), masks)
    levels = [0, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75]
    six_month_maps("sl_monthly_mean", da, "Average snow load by month, 1991–2020",
                   "Average snow load (lb/ft²); gray = glacier / perennial snow (masked)",
                   ORANGE_SEQ, BoundaryNorm(levels, 256, extend="max"), masks=masks, extend="max",
                   note="Source: disk1/Metrics/daily_SL_stats averageSL. Snow load = SWE × 5.2 lb/ft² per inch "
                        "(flat surface). Ocean blank.")


SL_BOUNDS = [0, 10, 20, 25, 48, 1e4]
SL_LABELS = ["< 10\ntentage OK", "10–20\nrigid shelters OK", "20–25\nlife-support OK", "25–48\nsemipermanent OK",
             "≥ 48\nexceeds all"]


def fig_sl_design_classes(sl, masks):
    typical = sl_land(sl.averageSL.max("day"), masks)
    record = sl_land(sl.max_SL.max("day"), masks)
    fig = plt.figure(figsize=(10.5, 6))
    axes = []
    for k, (da, t) in enumerate([(typical, "Typical peak: highest 30-year-average day"),
                                 (record, "Worst case: highest single hour in 30 winters")]):
        ax = polar_axes(fig, 1, 2, k + 1)
        m = draw_classes(ax, da, SL_BOUNDS, ORANGE[1:6])
        draw_glacier(ax, masks)
        ax.set_title(t, fontsize=9)
        axes.append(ax)
    class_colorbar(fig, m, axes, "Snow load (lb/ft²) against structure design loads (TR-26-5 §1)", SL_LABELS)
    fig.suptitle("Which structure design loads hold up? Typical vs. record snow load", fontsize=12,
                 fontweight="bold", x=0.02, ha="left")
    save(fig, "sl_design_classes",
         "Left: max over days of averageSL. Right: max over days of max_SL (true record of the 720 hours per day). "
         "Gray = glacier/perennial snow (masked). Ocean blank.")


def fig_sl_first_exceedance(sl, masks):
    avg = sl_land(sl.averageSL, masks)
    fig = plt.figure(figsize=(10.5, 6))
    axes = []
    # First-crossing day index binned by month; 183 = never crosses.
    bounds = [0, 31, 61, 92, 123, 152, 183, 1000]
    for k, thr in enumerate([10, 25]):
        ax = polar_axes(fig, 1, 2, k + 1)
        above = avg >= thr
        first = above.argmax("day").where(above.any("day"), 183).astype(float).where(avg.isel(day=0).notnull())
        m = draw_classes(ax, first, bounds, ORANGE[6:0:-1] + [NEVER])
        draw_glacier(ax, masks)
        ax.set_title(f"Average load first reaches {thr} lb/ft²", fontsize=9)
        axes.append(ax)
    class_colorbar(fig, m, axes, "Month in which the 30-year average snow load first crosses the threshold",
                   ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "never"])
    fig.suptitle("When does snow load arrive? First day the average crosses a design threshold",
                 fontsize=12, fontweight="bold", x=0.02, ha="left")
    save(fig, "sl_first_exceedance",
         "Reproduces SR-25-2 §3.6 from averageSL: first of the 183 days with 30-yr mean SL ≥ threshold. "
         "Mid-gray = glacier/perennial snow (masked).")


def fig_sl_points(sl, masks):
    pts = point_series(sl, masks)
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.2), sharex=True, sharey=True)
    for ax, (name, s) in zip(axes.flat, pts.items()):
        d = s.date.values
        ax.fill_between(d, s.percentile_50, s.percentile_95, color=ORANGE[2], alpha=0.5, lw=0,
                        label="50th–95th percentile hour")
        ax.plot(d, s.averageSL, color=ORANGE[4], lw=2, label="Average")
        ax.plot(d, s.max_SL, color=ORANGE[6], lw=1.2, ls=(0, (1, 1.5)), label="max_SL (30-yr record)")
        for y, t in [(10, "10"), (25, "25"), (48, "48")]:
            threshold_line(ax, y, t)
        ax.set_title(name, fontsize=9, loc="left")
        month_axis(ax, d)
        ax.set_ylim(0, 60)
        peak = float(s.max_SL.max())
        if peak > 60:
            ax.text(0.03, 0.97, f"record peaks at {peak:.0f} (off scale)", transform=ax.transAxes,
                    fontsize=7, color=INK2, va="top")
    axes[0, 0].set_ylabel("Snow load (lb/ft²)")
    axes[1, 0].set_ylabel("Snow load (lb/ft²)")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=3, fontsize=8, bbox_to_anchor=(0.99, 1.0))
    fig.suptitle("Snow load through the cold season at eight locations", fontsize=12, fontweight="bold",
                 x=0.01, ha="left", y=1.0)
    fig.tight_layout(rect=(0, 0.02, 0.97, 0.95))
    save(fig, "sl_points_seasonal", "Nearest land grid cell. The blip at Mar 1 is Feb 29 (only 8 leap years). Reference lines at 10 (tentage), 25 (life-support "
                                    "structures) and 48 lb/ft² (semipermanent structures).")


def fig_masks(masks):
    fig = plt.figure(figsize=(6.5, 6.8))
    ax = polar_axes(fig, 1, 1, 1)
    lm = masks.land.astype(float).where(masks.land)
    draw(ax, lm, cmap=ListedColormap([BLUE[1]]), vmin=0, vmax=1)
    draw_glacier(ax, masks)
    ax.set_title("Masks used: land (blue) and glacier / perennial snow (gray)", fontsize=10, loc="left")
    save(fig, "masks", "Land = non-NaN ERA5-Land snow depth (daily_SD_stats). Glacier = Oct 1 mean SL > 50 lb/ft² "
                       "or any hour within 5% of the 2047 lb/ft² ERA5 ice cap.")


FIGURES = {
    "masks": lambda c: fig_masks(c["masks"]),
    "wct_monthly_mean": lambda c: fig_wct_monthly_mean(c["wct"], c["masks"]),
    "wct_freq_m40": lambda c: fig_wct_freq_m40(c["wct"], c["masks"]),
    "wct_freq_m65": lambda c: fig_wct_freq_m65_season(c["wct"], c["masks"]),
    "wct_zones": lambda c: fig_wct_zones(c["wct"], c["masks"]),
    "wct_points": lambda c: fig_wct_points(c["wct"], c["masks"]),
    "wct_min_caveat": lambda c: fig_wct_min_caveat(),
    "wct_consecutive": lambda c: fig_wct_consecutive(c["wct"], c["masks"]),
    "sl_monthly_mean": lambda c: fig_sl_monthly_mean(c["sl"], c["masks"]),
    "sl_design": lambda c: fig_sl_design_classes(c["sl"], c["masks"]),
    "sl_first": lambda c: fig_sl_first_exceedance(c["sl"], c["masks"]),
    "sl_points": lambda c: fig_sl_points(c["sl"], c["masks"]),
}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(FIGURES)
    cubes = {"masks": load_masks()}
    if any(w.startswith("wct") for w in wanted):
        cubes["wct"] = load_cube("wct").load()
    if any(w.startswith("sl") for w in wanted):
        cubes["sl"] = load_cube("sl").load()
    for w in wanted:
        FIGURES[w](cubes)
