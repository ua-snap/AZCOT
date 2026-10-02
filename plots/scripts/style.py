"""Shared plotting style and map helpers for plots/ (palette from the dataviz skill, as in eda/)."""
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.path as mpath
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap
from matplotlib.patches import Patch

FIGS = Path(__file__).resolve().parents[1] / "figures"

SURFACE, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
        "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
ORANGE = ["#fdeee6", "#f9cdb7", "#f4a988", "#eb6834", "#c4501f", "#963a13", "#6b280b"]
GLACIER, PERENNIAL, NEVER = "#c9c8c2", "#8f8d86", "#f0efec"
# Status palette (fixed): frostbite danger levels always ship with a text label.
DANGER = {"green": "#0ca30c", "amber": "#fab219", "red": "#d03b3b"}
BLUE_SEQ = LinearSegmentedColormap.from_list("blue_seq", BLUE)
ORANGE_SEQ = LinearSegmentedColormap.from_list("orange_seq", ORANGE)
MONTHS = [10, 11, 12, 1, 2, 3]
MONTH_NAMES = {10: "October", 11: "November", 12: "December", 1: "January", 2: "February", 3: "March"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 9, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": BASE, "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlesize": 10,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
})
PROJ = ccrs.NorthPolarStereo(central_longitude=-100)


def ramp(color, name):
    """Single-hue sequential ramp from near-surface to a dark step of `color`."""
    c = np.array(matplotlib.colors.to_rgb(color))
    return LinearSegmentedColormap.from_list(name, [np.array([0.97, 0.97, 0.96]), c, c * 0.45])


def polar_axes(fig, nrows, ncols, idx, extent=(-180, 180, 60, 90)):
    ax = fig.add_subplot(nrows, ncols, idx, projection=PROJ)
    ax.set_extent(list(extent), ccrs.PlateCarree())
    if tuple(extent) == (-180, 180, 60, 90):
        theta = np.linspace(0, 2 * np.pi, 200)
        circle = mpath.Path(np.vstack([np.sin(theta), np.cos(theta)]).T * 0.5 + 0.5)
        ax.set_boundary(circle, transform=ax.transAxes)
    ax.coastlines("50m", linewidth=0.4, color=INK2)
    ax.gridlines(color=GRID, linewidth=0.4, xlocs=range(-180, 180, 30), ylocs=[60, 70, 80])
    return ax


def draw(ax, da, **kw):
    lon = np.append(da.lon.values.astype(float), float(da.lon[0]) + 360)  # wrap the dateline
    data = np.concatenate([da.values, da.values[..., :1]], axis=-1)
    return ax.pcolormesh(lon, da.lat.values, data, transform=ccrs.PlateCarree(), shading="nearest",
                         rasterized=True, **kw)


def draw_classes(ax, da, bounds, colors):
    idx = xr.apply_ufunc(lambda v: np.where(np.isnan(v), np.nan, np.digitize(v, bounds[1:-1])), da)
    n = len(colors)
    return draw(ax, idx, cmap=ListedColormap(colors), norm=BoundaryNorm(np.arange(-0.5, n), n))


def draw_surface_types(ax, st):
    """Symbolize glacier (2) and perennial snow (3) from the surface_type flag."""
    draw(ax, st.where(st == 2), cmap=ListedColormap([GLACIER]), vmin=0, vmax=3)
    draw(ax, st.where(st == 3), cmap=ListedColormap([PERENNIAL]), vmin=0, vmax=3)


def surface_legend(fig, loc="lower right", bbox=(0.99, 0.0)):
    fig.legend(handles=[Patch(color=GLACIER, label="glacier (ERA5 10 m w.e. cap)"),
                        Patch(color=PERENNIAL, label="perennial snow (never melts out)")],
               loc=loc, bbox_to_anchor=bbox, fontsize=7.5)


def colorbar(fig, mappable, axes, label, **kw):
    cb = fig.colorbar(mappable, ax=axes, orientation="horizontal", fraction=0.04, pad=0.03, aspect=40, **kw)
    cb.set_label(label, color=INK2)
    cb.outline.set_visible(False)
    if isinstance(mappable.norm, BoundaryNorm) and not np.allclose(np.diff(mappable.norm.boundaries), 1):
        cb.set_ticks(mappable.norm.boundaries)
        cb.ax.xaxis.set_major_formatter("{x:g}")
    return cb


def class_colorbar(fig, mappable, axes, label, ticklabels):
    cb = colorbar(fig, mappable, axes, label)
    cb.set_ticks(range(len(ticklabels)))
    cb.set_ticklabels(ticklabels, fontsize=7)
    cb.ax.tick_params(length=0)
    return cb


def six_month_maps(name, da, title, label, cmap, norm, st=None, note=None, extend="neither"):
    """da has a `time` dim with a `month` coordinate (monthly coverage)."""
    fig = plt.figure(figsize=(11, 8))
    axes = []
    for i, mon in enumerate(MONTHS):
        ax = polar_axes(fig, 2, 3, i + 1)
        m = draw(ax, da.sel(time=da.month == mon).squeeze("time"), cmap=cmap, norm=norm)
        if st is not None:
            draw_surface_types(ax, st)
        ax.set_title(MONTH_NAMES[mon], fontsize=9)
        axes.append(ax)
    fig.suptitle(title, fontsize=12, fontweight="bold", x=0.02, ha="left")
    colorbar(fig, m, axes, label, extend=extend)
    if st is not None:
        surface_legend(fig, bbox=(0.99, 0.06))
    save(fig, name, note)


def threshold_line(ax, y, text):
    ax.axhline(y, color=MUTED, lw=0.8, ls=(0, (4, 3)), zorder=1)
    ax.text(1.0, y, f" {text}", transform=ax.get_yaxis_transform(), va="center", ha="left",
            fontsize=7, color=MUTED, clip_on=False)


def month_axis(ax, dates):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_xlim(dates[0], dates[-1])


def save(fig, name, note=None):
    if note:
        fig.text(0.01, 0.005, note, fontsize=7, color=MUTED, ha="left", va="bottom")
    FIGS.mkdir(exist_ok=True)
    fig.savefig(FIGS / f"{name}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name, flush=True)
