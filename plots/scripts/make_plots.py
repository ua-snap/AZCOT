"""Figures for plots/plots.md, built only from the preprocessed coverages (preprocess/ outputs).

Usage: python make_plots.py [figure ...]   (default: all; names are the keys of FIGURES)
"""
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

from style import (BLUE, BLUE_SEQ, DANGER, GLACIER, INK, INK2, MONTH_NAMES, MONTHS, NEVER, ORANGE, ORANGE_SEQ,
                   PERENNIAL, SURFACE, class_colorbar, colorbar, draw, draw_classes, draw_surface_types,
                   month_axis, polar_axes, ramp, save, six_month_maps, surface_legend, threshold_line)

ROOT = Path(os.environ.get("AZCOT_PRE_OUT", "/import/beegfs/CMIP6/jdpaul3/azcot_preprocess"))
COV = ROOT / "coverages"
TABLES = Path(__file__).resolve().parents[1] / "tables"

LOCATIONS = [
    ("Fairbanks, AK", 64.84, -147.72), ("Utqiagvik, AK", 71.29, -156.79), ("Yellowknife, NT", 62.45, -114.37),
    ("Eureka, NU", 79.99, -85.93), ("Pituffik, GL", 76.53, -68.70), ("Tromsø, NO", 69.65, 18.96),
    ("Norilsk, RU", 69.35, 88.20), ("Oymyakon, RU", 63.46, 142.79),
]
# Frostbite danger levels (TR-26-5 Tables 4-5), approximated from wind chill; see plots.md.
FB_CUTS = {"green": (0, -20), "amber": (-20, -60), "red": (-60, None)}  # (upper, lower) WCT bounds in degF; hours with
# lower < WCT <= upper. Each bound must be one of the wct_frequency thresholds (0, -5, ..., -100).
FB_LABEL = {"green": "Slight danger (green): frostbite < 120 min, −20 < WCT ≤ 0 °F",
            "amber": "Increased danger (amber; TR-26-5 'orange'): frostbite < 45 min, −60 < WCT ≤ −20 °F",
            "red": "Great danger (red): frostbite ≤ 5 min, WCT ≤ −60 °F"}
PCT_LEVELS = [0, 1, 5, 10, 20, 30, 40, 50, 60, 80, 100]


def open_cov(var, kind, res):
    return xr.open_dataset(COV / f"azcot_{var}_{kind}_{res}.nc")


def land_cell(lat, lon, st, max_km=60):
    """Nearest seasonal-land cell (surface_type == 1)."""
    la2, lo2 = np.meshgrid(st.lat.values, st.lon.values, indexing="ij")
    dlon = np.radians(((lo2 - lon + 180) % 360) - 180)
    km = 6371 * np.arccos(np.clip(np.sin(np.radians(lat)) * np.sin(np.radians(la2)) + np.cos(np.radians(lat))
                                  * np.cos(np.radians(la2)) * np.cos(dlon), -1, 1))
    km = np.where(st.values == 1, km, np.inf)
    i, j = np.unravel_index(np.argmin(km), km.shape)
    assert km[i, j] <= max_km, (lat, lon)
    return i, j


def points(ds, st):
    return {n: ds.isel(lat=i, lon=j) for (n, la, lo) in LOCATIONS for i, j in [land_cell(la, lo, st)]}


# ---------------------------------------------------------------- section 4 re-plots: wind chill
def q1_wct_monthly_mean():
    da = open_cov("wct", "climatology", "monthly").wct_mean
    six_month_maps("q1_wct_monthly_mean", da, "Average wind chill by month, 1991–2020",
                   "Average wind chill (°F): mean of every hour in the month across 30 winters",
                   BLUE_SEQ.reversed(), BoundaryNorm(np.arange(-70, 31, 10), 256, extend="both"), extend="both",
                   note="Source: azcot_wct_climatology_monthly.nc, wct_mean.")


def q2_wct_freq_m40():
    da = open_cov("wct", "stats", "monthly").wct_frequency.sel(wct_threshold=-40)
    six_month_maps("q2_wct_freq_le_m40_monthly", da,
                   "How often wind chill is at or below −40 °F (frostbite in under 10 minutes)",
                   "Share of hours with wind chill ≤ −40 °F (%), 1991–2020", BLUE_SEQ, BoundaryNorm(PCT_LEVELS, 256),
                   note="Source: azcot_wct_stats_monthly.nc, wct_frequency(wct_threshold=-40).")


def q3_wct_freq_m65():
    season = open_cov("wct", "stats", "seasonal").wct_frequency.sel(wct_threshold=-65)
    peak = open_cov("wct", "stats", "monthly").wct_frequency.sel(wct_threshold=-65).max("time")
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
    save(fig, "q3_wct_freq_le_m65_season", "Sources: azcot_wct_stats_seasonal.nc and _monthly.nc (max over months).")


def q4_wct_zones():
    st = open_cov("wct", "climatology", "monthly").surface_type
    cm = open_cov("wct", "climatology", "monthly")
    jan_mean = cm.wct_mean.sel(time=cm.month == 1).squeeze("time")
    daily = open_cov("wct", "stats", "daily")
    jan_p1 = daily.wct_percentile.sel(percentile=1).sel(time=daily.month == 1).mean("time")
    bounds = [-200, -61, -51, -41, -25, -5, 20, 200]
    labels = ["5C\n< −61", "5B\n−51…−60", "5A\n−41…−50", "4\n−25…−40", "3\n−5…−24", "2\n19…−4", "1 or milder\n≥ 20"]
    fig = plt.figure(figsize=(10.5, 6))
    axes = []
    for k, (da, t) in enumerate([(jan_mean, "Typical January hour (average)"),
                                 (jan_p1, "Cold extreme: January 1st-percentile hour")]):
        ax = polar_axes(fig, 1, 2, k + 1)
        m = draw_classes(ax, da.where(st > 0), bounds, BLUE[12:5:-1])
        ax.set_title(t, fontsize=9)
        axes.append(ax)
    class_colorbar(fig, m, axes, "ATP 3-90.96 cold zone, applied to wind chill (°F)", labels)
    fig.suptitle("Which cold zone to equip for in January? Typical vs. 1-in-100-hour wind chill (land)",
                 fontsize=12, fontweight="bold", x=0.02, ha="left")
    save(fig, "q4_wct_cold_zones", "Left: climatology_monthly wct_mean. Right: January mean of daily "
                                   "wct_percentile(percentile=1). Land = surface_type > 0.")


def q5_wct_points():
    clim = open_cov("wct", "climatology", "daily")
    st = clim.surface_type
    pc = open_cov("wct", "stats", "daily").wct_percentile
    cp, pp = points(clim, st), points(pc, st)
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.2), sharex=True, sharey=True)
    for ax, name in zip(axes.flat, cp):
        c, p = cp[name].load(), pp[name].load()
        d = c.time.values
        ax.fill_between(d, p.sel(percentile=1), p.sel(percentile=50), color=BLUE[3], alpha=0.45, lw=0,
                        label="1st–50th percentile hour")
        ax.plot(d, c.wct_mean, color=BLUE[9], lw=2, label="Average")
        ax.plot(d, c.wct_min, color=BLUE[12], lw=1.2, ls=(0, (1, 1.5)), label="Record low (true minimum)")
        threshold_line(ax, -40, "−40")
        threshold_line(ax, -65, "−65")
        ax.set_title(name, fontsize=9, loc="left")
        month_axis(ax, d)
    for r in (0, 1):
        axes[r, 0].set_ylabel("Wind chill (°F)")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=3, fontsize=8, bbox_to_anchor=(0.99, 1.0))
    fig.suptitle("Wind chill through the cold season at eight locations", fontsize=12, fontweight="bold",
                 x=0.01, ha="left", y=1.0)
    fig.tight_layout(rect=(0, 0.02, 0.97, 0.95))
    save(fig, "q5_wct_points_seasonal", "Nearest seasonal-land cell. Daily climatology (182 days, no Feb 29). "
                                        "Dashed lines at −40 °F and −65 °F.")


def q6_wct_consecutive():
    sm = open_cov("wct", "stats", "monthly")
    jan = sm.sel(time=sm.month == 1).squeeze("time")
    fig = plt.figure(figsize=(10, 5.6))
    ax1 = polar_axes(fig, 1, 2, 1)
    m1 = draw(ax1, jan.wct_frequency.sel(wct_threshold=-40), cmap=BLUE_SEQ, norm=BoundaryNorm(PCT_LEVELS, 256))
    ax1.set_title("How often: % of January hours ≤ −40 °F", fontsize=9)
    ax2 = polar_axes(fig, 1, 2, 2)
    m2 = draw(ax2, jan.wct_consecutive.sel(wct_consec_threshold=-40), cmap=BLUE_SEQ,
              norm=BoundaryNorm([0, 1, 2, 4, 6, 8, 12, 16, 20, 24], 256))
    ax2.set_title("wct_consecutive: mean spell hours/day (no-spell years = 0)", fontsize=9)
    colorbar(fig, m1, [ax1], "%")
    colorbar(fig, m2, [ax2], "hours (max 24)")
    fig.suptitle("January: how often vs. the stored persistence metric for −40 °F wind chill", fontsize=12,
                 fontweight="bold", x=0.02, ha="left")
    save(fig, "q6_wct_jan_freq_vs_duration", "Source: azcot_wct_stats_monthly.nc. wct_consecutive mixes how often "
                                             "spells occur with how long they last; runs are cut at 00 UTC.")


# ---------------------------------------------------------------- section 4 re-plots: snow load
SL_BOUNDS = [0, 10, 20, 25, 48, 1e4]
SL_LABELS = ["< 10\ntentage OK", "10–20\nrigid shelters OK", "20–25\nlife-support OK", "25–48\nsemipermanent OK",
             "≥ 48\nexceeds all"]


def q7_sl_monthly_mean():
    ds = open_cov("sl", "climatology", "monthly")
    six_month_maps("q7_sl_monthly_mean", ds.sl_mean, "Average snow load by month, 1991–2020",
                   "Average snow load (lb/ft²)", ORANGE_SEQ,
                   BoundaryNorm([0, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75], 256, extend="max"), st=ds.surface_type,
                   extend="max", note="Source: azcot_sl_climatology_monthly.nc, sl_mean; glacier and perennial "
                                      "snow drawn from surface_type. Ocean blank.")


def q8_sl_design():
    typical = open_cov("sl", "climatology", "daily").sl_mean.max("time")
    seas = open_cov("sl", "climatology", "seasonal")
    fig = plt.figure(figsize=(10.5, 6))
    axes = []
    for k, (da, t) in enumerate([(typical, "Typical peak: highest 30-year-average day"),
                                 (seas.sl_max, "Worst case: highest single hour in 30 winters")]):
        ax = polar_axes(fig, 1, 2, k + 1)
        m = draw_classes(ax, da, SL_BOUNDS, ORANGE[1:6])
        draw_surface_types(ax, seas.surface_type)
        ax.set_title(t, fontsize=9)
        axes.append(ax)
    class_colorbar(fig, m, axes, "Snow load (lb/ft²) against structure design loads (TR-26-5 §1)", SL_LABELS)
    surface_legend(fig, bbox=(0.99, 0.12))
    fig.suptitle("Which structure design loads hold up? Typical vs. record snow load", fontsize=12,
                 fontweight="bold", x=0.02, ha="left")
    save(fig, "q8_sl_design_classes", "Left: max over days of climatology_daily sl_mean. Right: climatology_seasonal "
                                      "sl_max (true record).")


def q9_sl_first():
    ds = open_cov("sl", "climatology", "daily")
    avg = ds.sl_mean.load()
    fig = plt.figure(figsize=(10.5, 6))
    axes = []
    month_start = [0, 31, 61, 92, 123, 151, 182]  # day indices of Oct 1 ... Mar 1, end (no Feb 29)
    bounds = month_start + [1000]
    for k, thr in enumerate([10, 25]):
        ax = polar_axes(fig, 1, 2, k + 1)
        above = avg >= thr
        first = above.argmax("time").where(above.any("time"), 182).astype(float).where(avg.isel(time=0).notnull())
        m = draw_classes(ax, first, bounds, ORANGE[6:0:-1] + [NEVER])
        draw_surface_types(ax, ds.surface_type)
        ax.set_title(f"Average load first reaches {thr} lb/ft²", fontsize=9)
        axes.append(ax)
    class_colorbar(fig, m, axes, "Month in which the 30-year average snow load first crosses the threshold",
                   ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "never"])
    surface_legend(fig, bbox=(0.99, 0.12))
    fig.suptitle("When does snow load arrive? First day the average crosses a design threshold",
                 fontsize=12, fontweight="bold", x=0.02, ha="left")
    save(fig, "q9_sl_first_exceedance", "Source: azcot_sl_climatology_daily.nc sl_mean (SR-25-2 §3.6 method).")


def q10_sl_points():
    clim = open_cov("sl", "climatology", "daily")
    st = clim.surface_type
    pc = open_cov("sl", "stats", "daily").sl_percentile
    cp, pp = points(clim, st), points(pc, st)
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.2), sharex=True, sharey=True)
    for ax, name in zip(axes.flat, cp):
        c, p = cp[name].load(), pp[name].load()
        d = c.time.values
        ax.fill_between(d, p.sel(percentile=50), p.sel(percentile=95), color=ORANGE[2], alpha=0.5, lw=0,
                        label="50th–95th percentile hour")
        ax.plot(d, c.sl_mean, color=ORANGE[4], lw=2, label="Average")
        ax.plot(d, c.sl_max, color=ORANGE[6], lw=1.2, ls=(0, (1, 1.5)), label="Record high (true maximum)")
        for y in (10, 25, 48):
            threshold_line(ax, y, str(y))
        ax.set_title(name, fontsize=9, loc="left")
        month_axis(ax, d)
        ax.set_ylim(0, 60)
        peak = float(c.sl_max.max())
        if peak > 60:
            ax.text(0.03, 0.97, f"record peaks at {peak:.0f} (off scale)", transform=ax.transAxes, fontsize=7,
                    color=INK2, va="top")
    for r in (0, 1):
        axes[r, 0].set_ylabel("Snow load (lb/ft²)")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=3, fontsize=8, bbox_to_anchor=(0.99, 1.0))
    fig.suptitle("Snow load through the cold season at eight locations", fontsize=12, fontweight="bold",
                 x=0.01, ha="left", y=1.0)
    fig.tight_layout(rect=(0, 0.02, 0.97, 0.95))
    save(fig, "q10_sl_points_seasonal", "Nearest seasonal-land cell. Reference lines at 10 (tentage), 25 "
                                        "(life-support structures) and 48 lb/ft² (semipermanent structures).")


# ---------------------------------------------------------------- surface_type on snow load
def sl_surface_types():
    raw = xr.open_dataset(ROOT / "intermediate" / "surface_type.nc").season_max_sl  # unmasked, glaciers at cap
    seas = open_cov("sl", "climatology", "seasonal")
    st = seas.surface_type
    norm = BoundaryNorm([0, 10, 20, 25, 30, 40, 50, 75, 100], 256, extend="max")
    fig = plt.figure(figsize=(12, 12))
    # A: raw values with an honest linear scale to the data maximum.
    ax = polar_axes(fig, 2, 2, 1)
    m = draw(ax, raw.where(raw > 0), cmap=ORANGE_SEQ, vmin=0, vmax=2100)
    ax.set_title("A. Raw values, scale to data max: the glacier cap (2047)\nflattens every real load into the lightest color",
                 fontsize=9)
    colorbar(fig, m, [ax], "lb/ft²")
    # B: raw values on a useful scale.
    ax = polar_axes(fig, 2, 2, 2)
    m = draw(ax, raw.where(raw > 0), cmap=ORANGE_SEQ, norm=norm)
    ax.set_title("B. Raw values, useful scale: Greenland and the ice caps\nlook like the heaviest snow loads on Earth",
                 fontsize=9)
    colorbar(fig, m, [ax], "lb/ft²", extend="max")
    # C: coverage as stored (NaN outside land).
    ax = polar_axes(fig, 2, 2, 3)
    m = draw(ax, seas.sl_max, cmap=ORANGE_SEQ, norm=norm)
    ax.set_title("C. Coverage sl_max as stored (NaN): glaciers look like\nocean or missing data", fontsize=9)
    colorbar(fig, m, [ax], "lb/ft²", extend="max")
    # D: coverage + surface_type symbology.
    ax = polar_axes(fig, 2, 2, 4)
    m = draw(ax, seas.sl_max, cmap=ORANGE_SEQ, norm=norm)
    draw_surface_types(ax, st)
    ax.set_title("D. Coverage + surface_type: glaciers and perennial\nsnow drawn as their own classes", fontsize=9)
    colorbar(fig, m, [ax], "lb/ft²", extend="max")
    surface_legend(fig, bbox=(0.99, 0.03))
    fig.suptitle("Highest hourly snow load in 30 winters: four ways to draw the glacier cells", fontsize=13,
                 fontweight="bold", x=0.02, ha="left")
    save(fig, "sl_surface_types_4ways", "A–B: unmasked season max from intermediate/surface_type.nc. C–D: "
                                        "azcot_sl_climatology_seasonal.nc sl_max and surface_type.")


def sl_surface_types_zoom():
    seas = open_cov("sl", "climatology", "seasonal")
    raw = xr.open_dataset(ROOT / "intermediate" / "surface_type.nc").season_max_sl
    norm = BoundaryNorm([0, 10, 20, 25, 30, 40, 50, 75, 100], 256, extend="max")
    regions = [("Svalbard", (8, 32, 76, 81)), ("Iceland", (-25, -12, 63, 67))]
    fig = plt.figure(figsize=(11, 9))
    k = 1
    for name, ext in regions:
        for title, data, overlay in [("raw values", raw.where(raw > 0), False), ("coverage + surface_type", seas.sl_max, True)]:
            ax = polar_axes(fig, 2, 2, k, extent=ext)
            m = draw(ax, data, cmap=ORANGE_SEQ, norm=norm)
            if overlay:
                draw_surface_types(ax, seas.surface_type)
            ax.set_title(f"{name}: {title}", fontsize=9)
            k += 1
    colorbar(fig, m, fig.axes, "Highest hourly snow load, 1991–2020 (lb/ft²)", extend="max")
    surface_legend(fig, loc="upper right", bbox=(0.99, 0.99))
    fig.suptitle("Close-up: the perennial-snow ring around ERA5 glaciers", fontsize=12, fontweight="bold",
                 x=0.02, ha="left")
    save(fig, "sl_surface_types_zoom", "Raw (left): perennial-snow cells reach 500–2000 lb/ft² as snow piles up "
                                       "year after year. With the flag (right) they get their own class.")


# ---------------------------------------------------------------- frostbite danger levels
def fb_shares(ds):
    f = ds.wct_frequency  # % of hours with WCT <= threshold
    out = {}
    for cls, (upper, lower) in FB_CUTS.items():
        share = f.sel(wct_threshold=upper)
        if lower is not None:
            share = share - f.sel(wct_threshold=lower)
        out[cls] = share
    return out


def fb_monthly():
    shares = fb_shares(open_cov("wct", "stats", "monthly"))
    for cls in ("green", "amber", "red"):
        six_month_maps(f"fb_{cls}_monthly", shares[cls], f"Frostbite danger: {FB_LABEL[cls].split(':')[0]}",
                       f"Share of hours in this danger level (%), 1991–2020. {FB_LABEL[cls]}",
                       ramp(DANGER[cls], cls), BoundaryNorm(PCT_LEVELS, 256),
                       note="Approximated from wind chill (TR-26-5 Tables 4–5; see plots.md). "
                            "Source: azcot_wct_stats_monthly.nc wct_frequency.")


def fb_seasonal():
    shares = fb_shares(open_cov("wct", "stats", "seasonal"))
    fig = plt.figure(figsize=(14, 5.6))
    axes = []
    for k, cls in enumerate(("green", "amber", "red")):
        ax = polar_axes(fig, 1, 3, k + 1)
        m = draw(ax, shares[cls], cmap=ramp(DANGER[cls], cls), norm=BoundaryNorm(PCT_LEVELS, 256))
        ax.set_title(FB_LABEL[cls].split(":")[0], fontsize=9)
        colorbar(fig, m, [ax], "% of Oct–Mar hours")
        axes.append(ax)
    fig.suptitle("Frostbite danger levels over the whole cold season: share of hours in each level", fontsize=12,
                 fontweight="bold", x=0.02, ha="left")
    save(fig, "fb_seasonal_shares", "Green −20 < WCT ≤ 0 °F, amber −60 < WCT ≤ −20 °F, red WCT ≤ −60 °F. "
                                    "Source: azcot_wct_stats_seasonal.nc.")


def fb_dominant():
    ds = open_cov("wct", "stats", "monthly")
    s = fb_shares(ds)
    none = 100 - ds.wct_frequency.sel(wct_threshold=0)
    parts = [none, s["green"], s["amber"], s["red"]]
    stack = xr.concat([d.drop_vars("wct_threshold", errors="ignore") for d in parts], dim="cls")
    dom = stack.argmax("cls").astype(float)
    colors = ["#ecebe7", DANGER["green"], DANGER["amber"], DANGER["red"]]
    fig = plt.figure(figsize=(11, 8.2))
    axes = []
    for i, mon in enumerate(MONTHS):
        ax = polar_axes(fig, 2, 3, i + 1)
        m = draw(ax, dom.sel(time=dom.month == mon).squeeze("time"), cmap=ListedColormap(colors),
                 norm=BoundaryNorm(np.arange(-0.5, 4), 4))
        ax.set_title(MONTH_NAMES[mon], fontsize=9)
        axes.append(ax)
    class_colorbar(fig, m, axes, "Danger level that covers the most hours in the month",
                   ["no frostbite danger\n(WCT > 0 °F)", "slight (green)\n< 120 min", "increased (amber)\n< 45 min",
                    "great (red)\n≤ 5 min"])
    fig.suptitle("Most common frostbite danger level by month", fontsize=12, fontweight="bold", x=0.02, ha="left")
    save(fig, "fb_dominant_monthly", "Per cell and month: the class with the largest share of hours. Approximated "
                                     "from wind chill; see plots.md.")


# TR-26-5 Table 4, transcribed from the rendered page (values in degF; class colors W none, G, O, R).
T4_AIR = [40, 35, 30, 25, 20, 15, 10, 5, 0, -5, -10, -15, -20, -25, -30, -40, -45, -50]
T4_WIND = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
T4_WCT = """36 31 25 19 13 7 1 -5 -11 -16 -22 -28 -34 -40 -46 -52 -57 -63
34 27 21 15 9 3 -4 -10 -16 -22 -28 -35 -41 -47 -53 -59 -66 -72
32 25 19 13 6 6 -7 -13 -19 -26 -32 -39 -45 -51 -58 -64 -71 -77
30 24 17 11 4 4 -9 -15 -22 -29 -35 -42 -48 -55 -61 -68 -74 -81
29 23 16 9 3 3 -11 -17 -24 -31 -37 -44 -51 -58 -64 -71 -78 -84
28 22 15 8 1 1 -12 -19 -26 -33 -39 -46 -53 -60 -67 -73 -80 -87
28 21 14 7 0 0 -14 -21 -27 -34 -41 -48 -55 -62 -69 -76 -82 -89
27 20 13 6 -1 -1 -15 -22 -29 -36 -43 -50 -57 -64 -71 -78 -84 -91
26 19 12 5 -2 -2 -16 -23 -30 -37 -44 -51 -58 -65 -72 -79 -86 -93
26 19 12 4 -3 -3 -17 -24 -31 -38 -45 -52 -60 -67 -74 -81 -88 -95"""
T4_CLASS = """WWWGGGGGGGOOOOOOOO
WWWGGGGGGOOOOOOOOO
WWWGGGGGOOOOOOOORR
WWWGGGGGOOOOOOORRR
WWWGGGGOOOOOOORRRR
WWWGGGGOOOOOORRRRR
WWWGGGGOOOOORRRRRR
WWWGGGGOOOOORRRRRR
WWWGGGGOOOORRRRRRR
WWWGGGGOOOORRRRRRR"""


def fb_table4_check():
    wct = np.array([[int(v) for v in r.split()] for r in T4_WCT.splitlines()])
    tab = np.array([["WGOR".index(c) for c in r] for r in T4_CLASS.splitlines()])
    ours = np.select([wct <= -60, wct <= -20, wct <= 0], [3, 2, 1], 0)
    cmap = ListedColormap(["#ecebe7", DANGER["green"], DANGER["amber"], DANGER["red"]])
    fig, axes = plt.subplots(1, 2, figsize=(15, 4.6))
    for ax, cls, title in [(axes[0], tab, "TR-26-5 Table 4 as published (colors by frostbite time)"),
                           (axes[1], ours, "Wind-chill cut-offs used here: 0 / −20 / −60 °F")]:
        ax.imshow(cls, cmap=cmap, vmin=-0.5, vmax=3.5, aspect="auto")
        for i in range(wct.shape[0]):
            for j in range(wct.shape[1]):
                ax.text(j, i, wct[i, j], ha="center", va="center", fontsize=7,
                        color=SURFACE if cls[i, j] == 3 else INK)
                if cls is ours and ours[i, j] != tab[i, j]:
                    ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec=INK, lw=1.6))
        ax.set_xticks(range(len(T4_AIR)), T4_AIR)
        ax.set_yticks(range(len(T4_WIND)), T4_WIND)
        ax.set_xlabel("Air temperature (°F)")
        ax.set_ylabel("Wind speed (mph)")
        ax.grid(False)
        ax.set_title(title, fontsize=9, loc="left")
    n = int((ours != tab).sum())
    fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(cmap.colors, [
        "no class", "slight (green) < 120 min", "increased (amber/orange) < 45 min", "great (red) ≤ 5 min"])],
        loc="lower center", ncol=4, fontsize=8, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle(f"Same wind chill, different color: Table 4 vs. wind-chill-only classes ({n} of {wct.size} cells "
                 "differ, outlined)", fontsize=12, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.1, 1, 0.95))
    save(fig, "fb_table4_check", "Cell values: wind chill (°F) from TR-26-5 Table 4. Left colors transcribed from the "
                                 "published table; right colors from the wind-chill cut-offs.")


# ---------------------------------------------------------------- tables
def tables():
    TABLES.mkdir(exist_ok=True)
    cm, cs = open_cov("wct", "climatology", "monthly"), open_cov("wct", "climatology", "seasonal")
    ss, sm = open_cov("wct", "stats", "seasonal"), open_cov("wct", "stats", "monthly")
    sld, sls = open_cov("sl", "climatology", "daily"), open_cov("sl", "climatology", "seasonal")
    daily = open_cov("wct", "stats", "daily")
    st = cs.surface_type
    sh = fb_shares(ss)
    rows = []
    for name, la, lo in LOCATIONS:
        i, j = land_cell(la, lo, st)
        p = dict(lat=i, lon=j)
        jan = cm.isel(**p).sel(time=cm.month == 1)
        jan_p1 = daily.wct_percentile.sel(percentile=1).isel(**p).sel(time=daily.month == 1).mean()
        sl_avg = sld.sl_mean.isel(**p).values
        first25 = np.flatnonzero(sl_avg >= 25)
        rows.append({
            "location": name, "grid cell": f"{float(cs.lat[i]):.2f}, {float(cs.lon[j]):.2f}",
            "Jan avg WCT (°F)": round(float(jan.wct_mean.squeeze()), 1),
            "Jan 1st-pct WCT (°F)": round(float(jan_p1), 1),
            "record low WCT (°F)": round(float(cs.wct_min.isel(**p)), 1),
            "season % hrs ≤ −40": round(float(ss.wct_frequency.sel(wct_threshold=-40).isel(**p)), 1),
            "season % hrs ≤ −65": round(float(ss.wct_frequency.sel(wct_threshold=-65).isel(**p)), 2),
            "% hrs green": round(float(sh["green"].isel(**p)), 1),
            "% hrs amber": round(float(sh["amber"].isel(**p)), 1),
            "% hrs red": round(float(sh["red"].isel(**p)), 2),
            "peak avg SL": round(float(np.nanmax(sl_avg)), 1),
            "record SL": round(float(sls.sl_max.isel(**p)), 1),
            "avg SL ≥ 25 from": str(sld.calendar_day.values[first25[0]]).replace("_", " ") if first25.size else "never",
        })
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "locations.csv", index=False)
    print(df.to_markdown(index=False))


FIGURES = {
    "q1": q1_wct_monthly_mean, "q2": q2_wct_freq_m40, "q3": q3_wct_freq_m65, "q4": q4_wct_zones,
    "q5": q5_wct_points, "q6": q6_wct_consecutive, "q7": q7_sl_monthly_mean, "q8": q8_sl_design,
    "q9": q9_sl_first, "q10": q10_sl_points, "surface": sl_surface_types, "surface_zoom": sl_surface_types_zoom,
    "fb_monthly": fb_monthly, "fb_table4": fb_table4_check, "fb_seasonal": fb_seasonal, "fb_dominant": fb_dominant, "tables": tables,
}

if __name__ == "__main__":
    for name in sys.argv[1:] or FIGURES:
        FIGURES[name]()
