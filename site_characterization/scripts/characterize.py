"""Site characterization proof of concept: which equipment from TR-26-5 / ATP 3-90.96 / MIL-HDBK-310 / AR 70-38
works at a point, given the AZCOT coverages, and what can't be determined.

Reads only the preprocessed coverages (preprocess/). Writes site_characterization/sites/<site>.md.
Usage: python characterize.py [site-slug ...]
"""
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

HERE = Path(__file__).resolve().parents[1]
COV = Path(os.environ.get("AZCOT_PRE_OUT", "/import/beegfs/CMIP6/jdpaul3/azcot_preprocess")) / "coverages"
MONTHS = [10, 11, 12, 1, 2, 3]
MNAME = {10: "Oct", 11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar"}
CAUTION_SHARE = 0.01  # MIL-HDBK-310 / AR 70-38: 1% of hours in the month
CAUTION_YEARS = 0.10  # snowfall design loads (one event): "no" if reached in more than 1 year in 10

SITES = [
    ("Fairbanks, AK", 64.84, -147.72), ("Utqiagvik, AK", 71.29, -156.79), ("Yellowknife, NT", 62.45, -114.37),
    ("Eureka, NU", 79.99, -85.93), ("Pituffik, GL", 76.53, -68.70), ("Tromsø, NO", 69.65, 18.96),
    ("Norilsk, RU", 69.35, 88.20), ("Oymyakon, RU", 63.46, 142.79),
]
ZONES = [("1", 20, 39), ("2", -4, 19), ("3", -24, -5), ("4", -40, -25), ("5A", -50, -41), ("5B", -60, -51),
         ("5C", -999, -61)]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace("ø", "o")).strip("_")


def nearest(da_valid, lat, lon):
    """(i, j) of the nearest True cell of a 2-D boolean DataArray with lat/lon coords."""
    la2, lo2 = np.meshgrid(da_valid.lat.values, da_valid.lon.values, indexing="ij")
    dlon = np.radians(((lo2 - lon + 180) % 360) - 180)
    km = 6371 * np.arccos(np.clip(np.sin(np.radians(lat)) * np.sin(np.radians(la2))
                                  + np.cos(np.radians(lat)) * np.cos(np.radians(la2)) * np.cos(dlon), -1, 1))
    km = np.where(da_valid.values, km, np.inf)
    i, j = np.unravel_index(np.argmin(km), km.shape)
    return int(i), int(j), float(km[i, j])


class Hist:
    """Monthly histogram of hourly values at one cell. Bin u holds u-1 < x <= u."""

    def __init__(self, var, i, j):
        with xr.open_dataset(COV / f"azcot_{var}_histogram_monthly.nc") as ds:
            self.bins = ds["bin"].values
            self.counts = ds[f"{var}_hour_counts"].isel(lat=i, lon=j).values.astype(float)  # (6, nbin)
            self.n = ds["n_hours"].values.astype(float)
            self.months = list(ds["month"].values)

    def share_lt(self, x):
        """Share of hours below x per month (conservative: includes the bin containing x)."""
        return self.counts[:, self.bins <= math.ceil(x)].sum(axis=1) / self.n

    def share_ge(self, x):
        """Share of hours at or above x per month (conservative)."""
        return self.counts[:, self.bins > math.floor(x)].sum(axis=1) / self.n

    def band(self, lo, hi):
        lo_s = 0.0 if lo is None else self.share_lt(lo)
        hi_s = 1.0 if hi is None else self.share_lt(hi)
        return np.clip(hi_s - lo_s, 0, 1)

    def percentile(self, p):
        """Per-month p-th percentile (bin upper edge, 1-unit resolution)."""
        cum = np.cumsum(self.counts, axis=1) / self.n[:, None]
        return np.array([self.bins[np.argmax(c >= p / 100)] for c in cum])


def month_list(mask):
    ms = [MNAME[m] for m, k in zip(MONTHS, mask) if k]
    if not ms:
        return ""
    # compress consecutive runs in season order, e.g. Dec-Feb
    idx = [MONTHS.index(m) for m, k in zip(MONTHS, mask) if k]
    runs, start = [], idx[0]
    for a, b in zip(idx, idx[1:] + [None]):
        if b != a + 1:
            runs.append(MNAME[MONTHS[start]] if start == a else f"{MNAME[MONTHS[start]]}–{MNAME[MONTHS[a]]}")
            start = b
    return ", ".join(runs)


def verdict(record_fails, shares, limit=CAUTION_SHARE):
    """3-tier verdict per month -> (overall, caution months, no months)."""
    no = (shares > limit)
    caution = record_fails & ~no
    overall = "NO" if no.any() else "CAUTION" if caution.any() else "OK"
    return overall, month_list(caution), month_list(no)


def zone(t):
    """ATP 3-90.96 / TR-26-5 Table 2 cold zone of a temperature (degF)."""
    if t > 39:
        return "above zone 1"
    for name, lo, _ in ZONES:
        if t >= lo:
            return name
    return "5C"


def design_type(p1):
    for name, lim in [("C1 Basic cold", -25), ("C2 Cold", -50), ("C3 Severe cold", -60), ("C4 Extreme cold", -70)]:
        if p1 >= lim:
            return name
    return "colder than C4 (below -70 °F)"


def latlon(lat, lon):
    return f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'} {abs(lon):.2f}°{'E' if lon >= 0 else 'W'}"


def characterize(name, lat, lon, catalog):
    t2c = xr.open_dataset(COV / "azcot_t2_climatology_monthly.nc")
    st = t2c.surface_type
    i, j, dist = nearest(st == 1, lat, lon)
    sdc = xr.open_dataset(COV / "azcot_sd_climatology_monthly.nc")
    si, sj, sdist = nearest(sdc.sd_mean.isel(time=0).notnull(), lat, lon)
    p = dict(lat=i, lon=j)

    t2 = Hist("t2", i, j)
    ws = Hist("wspd", i, j)
    sd = Hist("sd", si, sj)
    t2_min = t2c.t2_min.isel(**p).values
    t2_mean = t2c.t2_mean.isel(**p).values
    ftd = t2c.t2_freeze_thaw_days.isel(**p).values
    wsc = xr.open_dataset(COV / "azcot_wspd_climatology_monthly.nc")
    ws_max = wsc.wspd_max.isel(**p).values
    sd_max = sdc.sd_max.isel(lat=si, lon=sj).values
    sd_mean = sdc.sd_mean.isel(lat=si, lon=sj).values
    slc = xr.open_dataset(COV / "azcot_sl_climatology_monthly.nc")
    sls = xr.open_dataset(COV / "azcot_sl_stats_monthly.nc")
    sl_max = slc.sl_max.isel(**p).values
    sl_mean = slc.sl_mean.isel(**p).values
    wct = xr.open_dataset(COV / "azcot_wct_stats_monthly.nc").wct_frequency.isel(**p)
    wct_s = xr.open_dataset(COV / "azcot_wct_stats_seasonal.nc").wct_frequency.isel(**p)
    stype = {0: "ocean", 1: "land", 2: "glacier", 3: "perennial snow"}[int(st.isel(**p))]
    snf = xr.open_dataset(COV / "azcot_snowfall_monthly.nc").isel(**p)
    snf_s = xr.open_dataset(COV / "azcot_snowfall_seasonal.nc").isel(**p)
    fbm = xr.open_dataset(COV / "azcot_frostbite_monthly.nc").isel(**p)
    fbs = xr.open_dataset(COV / "azcot_frostbite_seasonal.nc").isel(**p)

    p1 = t2.percentile(1)
    cold = int(np.argmin(t2_mean))
    results, bands, gaps = [], [], []
    for r in catalog.itertuples():
        lo = None if pd.isna(r.lo) else float(r.lo)
        hi = None if pd.isna(r.hi) else float(r.hi)
        if r.rule == "min_temp":
            ov, cm, nm = verdict(t2_min < lo, t2.share_lt(lo))
            results.append((r, ov, cm, nm, f"{lo:g} °F"))
        elif r.rule == "max_snow_depth":
            if hi is None:
                results.append((r, "OK", "", "", "no limit"))
                continue
            ov, cm, nm = verdict(sd_max >= hi, sd.share_ge(hi))
            results.append((r, ov, cm, nm, f"{hi:g} in"))
        elif r.rule == "max_snow_load":
            if stype != "land":
                results.append((r, "N/A", "", "", f"{hi:g} lb/ft² (cell is {stype})"))
                continue
            thr = hi if hi in (10, 20, 25) else 45.0
            shares = sls.sl_frequency.sel(sl_threshold=thr).isel(**p).values / 100
            ov, cm, nm = verdict(sl_max >= hi, shares)
            results.append((r, ov, cm, nm, f"{hi:g} lb/ft²"))
        elif r.rule == "max_snowfall_load":
            # one 24-hour snowfall (sf24) or one storm (storm); judged by the share of years reaching the limit
            years = snf[f"{r.variable}_ge{hi:g}_years"].values / 100
            ov, cm, nm = verdict(snf[f"{r.variable}_max"].values >= hi, years, CAUTION_YEARS)
            what = "24-hour snowfall" if r.variable == "sf24" else "storm total"
            results.append((r, ov, cm, nm, f"{hi:g} lb/ft² from one {what}"))
        elif r.rule == "max_wind":
            ov, cm, nm = verdict(ws_max >= hi, ws.share_ge(hi))
            results.append((r, ov, cm, nm, f"{hi:g} kn (hourly mean)"))
        elif r.rule == "band":
            h = t2 if r.variable == "t2" else ws
            bands.append((r, h.band(lo, hi)))
        elif r.rule == "missing" and isinstance(r.missing_data, str):
            gaps.append(r)
        # classify_* / frostbite / zone_tables / design_percentiles / freeze_thaw rows feed "At a glance".

    # ---- at-a-glance numbers
    season_hours = t2.n.sum()
    fb = {c: float(fbs[f"frostbite_{c}_share"]) for c in ("green", "amber", "red")}
    fb_red_m = fbm["frostbite_red_share"].values
    # Zones holding at least 0.1% of the season's hours (by 1-degF bin).
    season_share = t2.counts.sum(axis=0) / season_hours
    zones_reached = {zone(u) for u, sh in zip(t2.bins, season_share) if sh >= 0.001} - {"above zone 1"}
    pct = {q: t2.percentile(q)[cold] for q in (1, 5, 10)}

    L = []
    L.append(f"# {name}: site characterization\n")
    L.append(f"*Proof of concept. AZCOT ERA5 climatology 1991–2020, October–March. Grid cell "
             f"{latlon(float(st.lat[i]), float(st.lon[j]))} ({dist:.0f} km from the site, surface type: {stype}); snow depth from the "
             f"ERA5-Land cell {latlon(float(sdc.lat[si]), float(sdc.lon[sj]))}. See [README](../README.md) for "
             f"how verdicts are made and [data_gaps.md](../data_gaps.md) for what can't be determined.*\n")
    L.append("## At a glance\n")
    L.append("| | |\n|---|---|")
    L.append(f"| Coldest month | {MNAME[MONTHS[cold]]} (mean air temperature {t2_mean[cold]:.0f} °F) |")
    L.append(f"| Design cold, coldest month (1% / 5% / 10% of hours colder) | {pct[1]:.0f} / {pct[5]:.0f} / "
             f"{pct[10]:.0f} °F (MIL-HDBK-310 convention) |")
    L.append(f"| Record low air temperature (30 winters) | {np.min(t2_min):.0f} °F ({MNAME[MONTHS[int(np.argmin(t2_min))]]}) |")
    L.append(f"| AR 70-38 climatic design type | **{design_type(np.min(p1))}** (from the coldest-month 1% value) |")
    L.append(f"| ATP 3-90.96 cold zone: typical / design / record | {zone(t2_mean[cold])} / {zone(np.min(p1))} / "
             f"{zone(np.min(t2_min))} |")
    L.append(f"| Safety tables that apply (ATP 3-90.96 App. F) | "
             + ", ".join(f"F-{k} / F-{k + 5}" for k in sorted({int(z[0]) for z in zones_reached})) + " |")
    L.append(f"| Frostbite danger (TR-26-5 Eq. 5), share of Oct–Mar hours | green {fb['green']:.0f}% · amber {fb['amber']:.0f}% · "
             f"red {fb['red']:.1f}% " + (f"(red peaks at {np.max(fb_red_m):.1f}% in {MNAME[MONTHS[int(np.argmax(fb_red_m))]]})"
                                       if np.max(fb_red_m) >= 0.05 else "(red never reached)") + " |")
    L.append(f"| Freeze-thaw days per winter | {np.sum(ftd):.0f} (" + ", ".join(
        f"{MNAME[m]} {v:.0f}" for m, v in zip(MONTHS, ftd) if v >= 0.5) + ") |")
    L.append(f"| Snow depth: typical peak / record | {np.max(sd_mean):.0f} / {np.max(sd_max):.0f} in |")
    if stype == "land":
        L.append(f"| Snow load: typical peak / record | {np.max(sl_mean):.0f} / {np.max(sl_max):.0f} lb/ft² |")
    else:
        L.append(f"| Snow load | not meaningful (cell is {stype}) |")
    L.append(f"| Snowfall load: record 24-hour / 72-hour / storm total | {float(snf_s.sf24_max):.1f} / "
             f"{float(snf_s.sf72_max):.1f} / {float(snf_s.storm_max):.1f} lb/ft² (tentage limit 10, rigid shelters 20; "
             "storm = snowfall with lulls of at most 12 h, a definition we chose: see "
             "[storm definition](../../preprocess/storm_definition/README.md)) |")
    L.append(f"| Wind (10 m hourly mean): record | {np.max(ws_max):.0f} kn (hourly mean; gusts not used, see data gaps) |\n")

    L.append("## Shopping list\n")
    L.append("**OK** = the 30-year record low (or high) never crosses the item's limit. **Caution** = only rare hours "
             "(≤ 1% of a month) cross it, in the months named. **No** = more than 1% of hours cross it, in the months "
             "named. Limits are shown in parentheses.\n")
    for cat in dict.fromkeys(r.category for r, *_ in results):
        rows = [x for x in results if x[0].category == cat]
        L.append(f"**{cat}**\n")
        for tier, label in (("OK", "OK"), ("CAUTION", "Caution"), ("NO", "No"), ("N/A", "N/A")):
            items = [x for x in rows if x[1] == tier]
            if not items:
                continue
            if tier in ("OK", "N/A"):
                L.append(f"- {label}: " + "; ".join(f"{r.item} ({lim})" for r, _, _, _, lim in items))
            else:
                parts = []
                for r, _, cm, nm, lim in items:
                    when = f"no in {nm}" + (f", caution in {cm}" if cm else "") if tier == "NO" else f"in {cm}"
                    parts.append(f"{r.item} ({lim}; {when})")
                L.append(f"- {label}: " + "; ".join(parts))
        L.append("")

    L.append("## Use-when guidance (share of hours in each band, by month)\n")
    L.append("| Guidance | " + " | ".join(MNAME[m] for m in MONTHS) + " |")
    L.append("|---|" + "---:|" * 6)
    for r, sh in bands:
        if r.band == "use":
            L.append(f"| {r.item} | " + " | ".join(f"{100 * v:.0f}%" if v >= 0.005 else "·" for v in sh) + " |")
    L.append("")
    L.append("## Operations stoplight (wind or temperature only; share of Oct–Mar hours)\n")
    L.append("Partial: TR-26-5 Table 6 also needs ceiling, visibility, precipitation, turbulence, icing and gusts "
             "(see [data_gaps.md](../data_gaps.md)).\n")
    L.append("| Operation | Favorable | Marginal | Unfavorable | Worst month (unfavorable) |")
    L.append("|---|---:|---:|---:|---|")
    ops = {}
    for r, sh in bands:
        if r.band in ("favorable", "marginal", "unfavorable"):
            ops.setdefault(r.item, {})[r.band] = sh
    for op, d in ops.items():
        h = t2 if "temperature" in op else ws
        season = {k: float((v * h.n).sum() / h.n.sum()) for k, v in d.items()}
        unf = d.get("unfavorable", np.zeros(6))
        k = int(np.argmax(unf))
        L.append(f"| {op} | {100 * season.get('favorable', 0):.0f}% | "
                 + (f"{100 * season['marginal']:.0f}%" if "marginal" in season else "—")
                 + f" | {100 * season.get('unfavorable', 0):.1f}% | "
                 + (f"{MNAME[MONTHS[k]]} {100 * unf[k]:.1f}%" if unf[k] > 0 else "never") + " |")
    L.append("")
    L.append("## Not determined from AZCOT data\n")
    for r in gaps:
        L.append(f"- {r.item} ({r.source} {r.table}): needs {r.missing_data}")
    L.append("")
    out = HERE / "sites" / f"{slug(name)}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L))
    print("wrote", out)
    return {"site": name, "slug": slug(name), "design_type": design_type(np.min(p1)),
            "zone_design": zone(np.min(p1)), "record_low": float(np.min(t2_min)),
            "n_ok": sum(x[1] == "OK" for x in results), "n_caution": sum(x[1] == "CAUTION" for x in results),
            "n_no": sum(x[1] == "NO" for x in results), "n_items": len(results)}


def main():
    catalog = pd.read_csv(HERE / "thresholds.csv")
    wanted = set(sys.argv[1:])
    summary = [characterize(n, la, lo, catalog) for n, la, lo in SITES if not wanted or slug(n) in wanted]
    pd.DataFrame(summary).to_csv(HERE / "sites" / "summary.csv", index=False)


if __name__ == "__main__":
    main()
