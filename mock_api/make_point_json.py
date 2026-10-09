"""Mock AZCOT point-query API response (JSON) for one site, built from the Rasdaman-ready coverages.

The values are real: they are read from the same files the draft Rasdaman recipes ingest
(<OUT_ROOT>/rasdaman/<coverage_id>.nc, see rasdaman/README.md), at the grid cell an API would pick. The endpoint,
field names and nesting are a proposal for the application to build against; see mock_api/README.md.

Covered: climatology statistics (air temperature, wind chill, wind speed, snow depth, snow load, freeze-thaw days),
design cold and cold zones, exceedance frequencies, frostbite danger classes, snowfall design loads, and OK / Caution /
No verdicts for the climate-limit rows of the threshold catalog (snow loads, structure wind, vehicles vs snow depth).
Equipment, clothing, fuel etc. verdicts (the site pages' "shopping list") are deliberately left out.

Usage: python make_point_json.py [--name "Fairbanks, AK" --lat 64.84 --lon -147.72] [--out fairbanks_ak.json]
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "preprocess"))
sys.path.insert(0, str(HERE.parent / "site_characterization" / "scripts"))
from config import OUT_ROOT  # noqa: E402
from characterize import (CAUTION_SHARE, CAUTION_YEARS, ZONES, design_type, nearest, slug,  # noqa: E402
                          zone)

PREP = OUT_ROOT / "rasdaman"
SEASON = [10, 11, 12, 1, 2, 3]
MNAME = {10: "oct", 11: "nov", 12: "dec", 1: "jan", 2: "feb", 3: "mar"}
CATALOG = HERE.parent / "site_characterization" / "thresholds.csv"
CLIMATE_RULES = ("max_snow_depth", "max_snow_load", "max_snowfall_load", "max_wind")


def r(x, nd=2):
    x = float(x)
    return None if not np.isfinite(x) else round(x, nd)


class Point:
    """Reads bands at one cell from Rasdaman-ready coverage files and records which coverages were used."""

    def __init__(self, i, j, si, sj):
        self.cell = {"era5": (i, j), "era5land": (si, sj)}
        self._open = {}
        self.used = {}

    def ds(self, cid):
        if cid not in self._open:
            self._open[cid] = xr.open_dataset(PREP / f"{cid}.nc")
        return self._open[cid]

    def band(self, cid, band, grid="era5"):
        ds = self.ds(cid)
        i, j = self.cell[grid]
        da = ds[band].isel(lat=i, lon=j)
        self.used.setdefault(cid, {"bands": set(), "lat": float(ds.lat[i]), "lon": float(ds.lon[j])})
        self.used[cid]["bands"].add(band)
        return da


def by_month(da):
    return {MNAME[m]: r(da.sel(month=m)) for m in SEASON}


def by_day(da):
    out = {}
    for m in SEASON:
        for v in da.mmdd.values[(da.mmdd.values // 100) == m]:
            out[f"{MNAME[m]}_{int(v) % 100:02d}"] = r(da.sel(mmdd=v))
    return out


def src(cid, band, axis):
    return {"coverage_id": cid, "band": band, "axis": axis}


def wcps(cid, band, lat, lon):
    return (f'for $c in ({cid}) return encode($c.{band}[lat({lat:g}), lon({lon:g})], "application/json")')


def three_res(p, stem, band, grid="era5"):
    """{daily, monthly, seasonal} values of one band from <stem>_{daily,monthly,seasonal} coverages."""
    return {"daily": by_day(p.band(f"{stem}_daily", band, grid)),
            "monthly": by_month(p.band(f"{stem}_monthly", band, grid)),
            "seasonal": r(p.band(f"{stem}_seasonal", band, grid))}


def three_src(stem, band):
    return {"daily": src(f"{stem}_daily", band, "mmdd"), "monthly": src(f"{stem}_monthly", band, "month"),
            "seasonal": src(f"{stem}_seasonal", band, None)}


class Hist:
    """Monthly hourly-value histogram at the cell (bin u holds u-1 < x <= u)."""

    def __init__(self, p, cid, band, grid="era5"):
        da = p.band(cid, band, grid)
        self.bins = da["bin"].values
        self.counts = np.stack([da.sel(month=m).values.astype(float) for m in SEASON])  # (6, nbin), season order
        self.n = self.counts.sum(axis=1)

    def share_le(self, t):  # % of hours <= t (integer t)
        return self.counts[:, self.bins <= t].sum(axis=1) / self.n * 100

    def share_gt(self, t):  # % of hours > t
        return self.counts[:, self.bins > t].sum(axis=1) / self.n * 100

    def season(self, monthly_share):
        return float((monthly_share * self.n).sum() / self.n.sum())

    def percentile(self, q):
        cum = np.cumsum(self.counts, axis=1) / self.n[:, None]
        return np.array([self.bins[np.argmax(c >= q / 100)] for c in cum])


CLIM_VARS = {
    "air_temperature": ("t2", "degF", "2 m air temperature (ERA5)", None),
    "wind_chill": ("wct", "degF", "Wind chill temperature (AZCOT, NWS 2001 formula)",
                   "AZCOT computed wind chill from SKIN temperature, not the 2 m air temperature TR-26-5 states; over "
                   "land in January it runs ~3.5 degF colder (AZCOT_DATA_ISSUES.md, issue 10)."),
    "wind_speed": ("wspd", "knots", "10 m wind speed, hourly mean (ERA5); no gusts", None),
    "snow_depth": ("sd", "inches", "Snow depth (ERA5-Land, 0.1 degree grid)",
                   "The source is missing hours 01-23 UTC of the last day of every month; those days rest on 30 hourly "
                   "values instead of 720."),
    "snow_load": ("sl", "lbf/ft2", "Snow load of the snowpack on a flat surface, SWE[in] x 5.2 (TR-26-5 eq. 4)", None),
}


def climatology(p, lat, lon):
    out = {}
    for name, (v, units, title, note) in CLIM_VARS.items():
        grid = "era5land" if v == "sd" else "era5"
        stem = f"azcot_{v}_climatology"
        block = {"title": title, "units": units,
                 "description": "Daily: lowest / mean / highest of the 720 hourly values (30 years x 24 h) for that "
                                "calendar day. Monthly and seasonal: lowest of the daily lows, mean of the daily means, "
                                "highest of the daily highs. min and max are true 30-year records.",
                 "source": {s: three_src(stem, f"{v}_{s}") for s in ("min", "mean", "max")}}
        if note:
            block["caveat"] = note
        for s in ("min", "mean", "max"):
            block[s] = three_res(p, stem, f"{v}_{s}", grid)
        out[name] = block
    out["freeze_thaw_days"] = {
        "title": "Freeze-thaw days per year (hourly air temperature both below and above 32 degF on the same day)",
        "units": "days", "source": {"monthly": src("azcot_t2_climatology_monthly", "t2_freeze_thaw_days", "month"),
                                    "seasonal": src("azcot_t2_climatology_seasonal", "t2_freeze_thaw_days", None)},
        "value": {"monthly": by_month(p.band("azcot_t2_climatology_monthly", "t2_freeze_thaw_days")),
                  "seasonal": r(p.band("azcot_t2_climatology_seasonal", "t2_freeze_thaw_days"))}}
    return out


def design(p, t2h):
    t2mean = by_month(p.band("azcot_t2_climatology_monthly", "t2_mean"))
    t2min = p.band("azcot_t2_climatology_monthly", "t2_min")
    mins = {MNAME[m]: float(t2min.sel(month=m)) for m in SEASON}
    cold = min(t2mean, key=t2mean.get)
    p1, p5, p10 = (t2h.percentile(q) for q in (1, 5, 10))
    ci = list(t2mean).index(cold)
    rec_month = min(mins, key=mins.get)
    return {
        "title": "Design cold and cold zones",
        "units": "degF",
        "source": {"air_temperature_histogram": src("azcot_t2_hour_counts_monthly", "t2_hour_counts", "month"),
                   "air_temperature_climatology": src("azcot_t2_climatology_monthly", "t2_min, t2_mean", "month")},
        "coldest_month": {"month": cold, "mean_air_temperature": t2mean[cold]},
        "design_cold": {
            "description": "Air temperature exceeded on the cold side by 1 / 5 / 10% of hours (MIL-HDBK-310 "
                           "convention), from the monthly 1 degF histograms (value = bin upper edge).",
            "coldest_month": {"1pct": float(p1[ci]), "5pct": float(p5[ci]), "10pct": float(p10[ci])},
            "monthly": {"1pct": dict(zip(t2mean, map(float, p1))), "5pct": dict(zip(t2mean, map(float, p5))),
                        "10pct": dict(zip(t2mean, map(float, p10)))}},
        "record_low": {"value": r(mins[rec_month]), "month": rec_month},
        "ar70_38_design_type": {
            "value": design_type(float(np.min(p1))),
            "basis": "lowest monthly 1% value; C1 >= -25, C2 >= -50, C3 >= -60, C4 >= -70 degF (AR 70-38 / TR-26-5 "
                     "Table 1)"},
        "atp_cold_zone": {
            "typical": zone(t2mean[cold]), "design": zone(float(np.min(p1))), "record": zone(mins[rec_month]),
            "basis": "ATP 3-90.96 Table 1-3 / TR-26-5 Table 2 zone of the coldest-month mean (typical), the lowest "
                     "monthly 1% value (design) and the 30-year record low (record)",
            "zones_degF": {z: {"from": lo if lo > -999 else None, "to": hi} for z, lo, hi in ZONES}},
    }


def exceed_hist(h, thresholds, kind):
    out = {}
    for t in thresholds:
        m = h.share_le(t) if kind == "le" else h.share_gt(t)
        out[f"{t:g}"] = {"monthly": dict(zip([MNAME[x] for x in SEASON], map(r, m))), "seasonal": r(h.season(m))}
    return out


def exceed_freq(p, stem, band, axis, thresholds):
    out = {}
    for t in thresholds:
        out[f"{t:g}"] = {
            "daily": by_day(p.band(f"{stem}_daily", band).sel({axis: t})),
            "monthly": by_month(p.band(f"{stem}_monthly", band).sel({axis: t})),
            "seasonal": r(p.band(f"{stem}_seasonal", band).sel({axis: t}))}
    return out


def exceedance(p, t2h, wsh, sdh):
    return {
        "description": "Share of hours (%) beyond each threshold. Monthly and seasonal for every variable; daily as well "
                       "where a daily coverage exists (wind chill, snow load). Histogram-based values are exact to the "
                       "1-unit bin; any other threshold can be computed from the *_hour_counts coverages.",
        "air_temperature_at_or_below": {
            "units": "% of hours", "threshold_units": "degF",
            "source": src("azcot_t2_hour_counts_monthly", "t2_hour_counts", "month, bin"),
            "thresholds": exceed_hist(t2h, [32, 0, -20, -25, -40, -50, -60, -65], "le")},
        "wind_chill_at_or_below": {
            "units": "% of hours", "threshold_units": "degF",
            "caveat": CLIM_VARS["wind_chill"][3],
            "source": {"daily": src("azcot_wct_frequency_daily", "wct_frequency", "mmdd, wct_threshold"),
                       "monthly": src("azcot_wct_frequency_monthly", "wct_frequency", "month, wct_threshold"),
                       "seasonal": src("azcot_wct_frequency_seasonal", "wct_frequency", "wct_threshold")},
            "thresholds": exceed_freq(p, "azcot_wct_frequency", "wct_frequency", "wct_threshold",
                                      [0, -20, -40, -60, -65])},
        "wind_speed_above": {
            "units": "% of hours", "threshold_units": "knots (hourly mean)",
            "source": src("azcot_wspd_hour_counts_monthly", "wspd_hour_counts", "month, bin"),
            "thresholds": exceed_hist(wsh, [12, 20, 30, 45, 87], "gt")},
        "snow_depth_above": {
            "units": "% of hours", "threshold_units": "inches",
            "source": src("azcot_sd_hour_counts_monthly", "sd_hour_counts", "month, bin"),
            "thresholds": exceed_hist(sdh, [8, 15, 20, 40], "gt")},
        "snow_load_at_or_above": {
            "units": "% of hours", "threshold_units": "lbf/ft2",
            "source": {"daily": src("azcot_sl_frequency_daily", "sl_frequency", "mmdd, sl_threshold"),
                       "monthly": src("azcot_sl_frequency_monthly", "sl_frequency", "month, sl_threshold"),
                       "seasonal": src("azcot_sl_frequency_seasonal", "sl_frequency", "sl_threshold")},
            "thresholds": exceed_freq(p, "azcot_sl_frequency", "sl_frequency", "sl_threshold",
                                      [10, 20, 25, 30, 40, 50])},
    }


FB_CLASSES = {
    "red": {"label": "Great danger", "tr26_5_color": "red", "minutes": "FT <= 5"},
    "amber": {"label": "Increased danger", "tr26_5_color": "orange", "minutes": "5 < FT <= 45"},
    "green": {"label": "Slight danger", "tr26_5_color": "green", "minutes": "45 < FT <= 120"},
    "none": {"label": "No frostbite danger", "tr26_5_color": None,
             "minutes": "FT > 120, or air temperature >= 23.36 degF (Eq. 5 undefined)"},
}


def frostbite(p):
    return {
        "title": "Frostbite danger levels (TR-26-5 Tables 4-5)",
        "description": "Time to frostbite of exposed, dry cheek skin, computed for every hour from 2 m air temperature "
                       "and 10 m wind with TR-26-5 Eq. 5 (Nelson et al. 2002), then counted per danger level. Uses air "
                       "temperature (not AZCOT's skin-temperature wind chill). Eq. 5 does not reproduce every value of "
                       "TR-26-5 Table 5.",
        "classes": FB_CLASSES,
        "share_units": "% of hours",
        "source": {f"{c}_share": three_src("azcot_frostbite", f"frostbite_{c}_share") for c in FB_CLASSES},
        "share": {c: three_res(p, "azcot_frostbite", f"frostbite_{c}_share") for c in FB_CLASSES},
        "shortest_time_to_frostbite": {
            "units": "minutes", "description": "Shortest time to frostbite in any hour of 30 years (true minimum)",
            "source": three_src("azcot_frostbite", "frostbite_time_min"),
            "value": three_res(p, "azcot_frostbite", "frostbite_time_min")},
    }


SF_BANDS = {
    "sf24_max": ("lbf/ft2", "Record 24-hour snowfall load (largest trailing 24-hour snowfall in 30 years)"),
    "sf24_mean_annual_max": ("lbf/ft2", "Mean over 30 years of each year's largest 24-hour snowfall load"),
    "sf24_ge10_years": ("% of years", "Years with at least one 24-hour load >= 10 lbf/ft2 (tentage)"),
    "sf24_ge10_days": ("days per year", "Days per year whose largest 24-hour load is >= 10 lbf/ft2"),
    "storm_max": ("lbf/ft2", "Record storm-total snowfall load"),
    "storm_mean_annual_max": ("lbf/ft2", "Mean over 30 years of each year's largest storm total"),
    "storm_ge20_years": ("% of years", "Years with at least one storm total >= 20 lbf/ft2 (rigid shelters)"),
    "storm_ge20_per_year": ("storms per year", "Storms per year with a total >= 20 lbf/ft2"),
    "sf72_max": ("lbf/ft2", "Record 72-hour snowfall load (needs no storm definition)"),
    "sf72_mean_annual_max": ("lbf/ft2", "Mean over 30 years of each year's largest 72-hour load"),
}


def snowfall(p):
    out = {"title": "Snowfall design loads (TR-26-5 section 1)",
           "description": "From ERA5 hourly snowfall (SNAP ERA5 holdings), water equivalent x 204.7 lbf/ft2 per m. "
                          "Tentage must carry 10 lbf/ft2 from one 24-hour snowfall; rigid shelters 20 lbf/ft2 from one "
                          "storm, cleared between storms. A 'year' is the Jan-Mar plus Oct-Dec of one calendar year.",
           "storm_definition": "Our choice (TR-26-5 gives none): hours with snowfall >= 0.1 mm water equivalent, dry "
                               "gaps of at most 12 h inside one storm; total from first to last wet hour, credited to "
                               "the day the storm ends. See preprocess/storm_definition/README.md.",
           "variables": {}}
    for band, (units, title) in SF_BANDS.items():
        per_year = band.endswith(("_days", "_per_year"))
        v = {"title": title, "units": units}
        if per_year:  # monthly and seasonal only
            v["source"] = {"monthly": src("azcot_snowfall_monthly", band, "month"),
                           "seasonal": src("azcot_snowfall_seasonal", band, None)}
            v["value"] = {"monthly": by_month(p.band("azcot_snowfall_monthly", band)),
                          "seasonal": r(p.band("azcot_snowfall_seasonal", band))}
        else:
            v["source"] = three_src("azcot_snowfall", band)
            v["value"] = three_res(p, "azcot_snowfall", band)
        out["variables"][band] = v
    return out


def month_classes(record_fails, shares, limit):
    cls = np.where(shares > limit, "NO", np.where(record_fails, "CAUTION", "OK"))
    return dict(zip([MNAME[m] for m in SEASON], cls.tolist()))


def overall(by_month_cls):
    v = list(by_month_cls.values())
    return "NO" if "NO" in v else "CAUTION" if "CAUTION" in v else "OK"


def verdicts(p, stype, sdh, wsh):
    cat = pd.read_csv(CATALOG)
    cat = cat[cat.rule.isin(CLIMATE_RULES)]
    months = [MNAME[m] for m in SEASON]
    items = []
    for row in cat.itertuples():
        hi = None if pd.isna(row.hi) else float(row.hi)
        item = {"id": row.id, "source_document": row.source, "table": row.table, "category": row.category,
                "item": row.item, "limit": {"value": hi, "units": row.units}}
        if row.rule == "max_snow_depth":
            item["limit"]["test"] = "snow depth above the limit"
            if hi is None:
                item.update(verdict="OK", by_month={m: "OK" for m in months},
                            basis="No upper limit (over-snow vehicles are the answer where snow is deeper than 40 in)")
                items.append(item)
                continue
            rec = p.band("azcot_sd_climatology_monthly", "sd_max", "era5land")
            rec = np.array([float(rec.sel(month=m)) for m in SEASON])
            shares = sdh.share_gt(np.floor(hi))
            lim, share_def = CAUTION_SHARE, "% of hours with snow depth above the limit"
            sources = [src("azcot_sd_climatology_monthly", "sd_max", "month"),
                       src("azcot_sd_hour_counts_monthly", "sd_hour_counts", "month, bin")]
        elif row.rule == "max_snow_load":
            item["limit"]["test"] = "snowpack load at or above the limit"
            if stype != "land":
                item.update(verdict="N/A", by_month={m: "N/A" for m in months}, basis=f"cell is {stype}")
                items.append(item)
                continue
            thr = hi if hi in (10, 20, 25) else 45.0
            rec = p.band("azcot_sl_climatology_monthly", "sl_max")
            rec = np.array([float(rec.sel(month=m)) for m in SEASON])
            f = p.band("azcot_sl_frequency_monthly", "sl_frequency").sel(sl_threshold=thr)
            shares = np.array([float(f.sel(month=m)) for m in SEASON])
            lim, share_def = CAUTION_SHARE, f"% of hours with snow load >= {thr:g} lbf/ft2"
            sources = [src("azcot_sl_climatology_monthly", "sl_max", "month"),
                       src("azcot_sl_frequency_monthly", "sl_frequency", "month, sl_threshold")]
        elif row.rule == "max_snowfall_load":
            v = row.variable  # sf24 | storm
            item["limit"]["test"] = ("one 24-hour snowfall at or above the limit" if v == "sf24"
                                     else "one storm total at or above the limit")
            rec = p.band("azcot_snowfall_monthly", f"{v}_max")
            rec = np.array([float(rec.sel(month=m)) for m in SEASON])
            yrs = p.band("azcot_snowfall_monthly", f"{v}_ge{hi:g}_years")
            shares = np.array([float(yrs.sel(month=m)) for m in SEASON])
            lim, share_def = CAUTION_YEARS, f"% of years in which the month had a {v} load >= {hi:g} lbf/ft2"
            sources = [src("azcot_snowfall_monthly", f"{v}_max", "month"),
                       src("azcot_snowfall_monthly", f"{v}_ge{hi:g}_years", "month")]
        else:  # max_wind
            item["limit"]["test"] = "hourly-mean 10 m wind at or above the limit"
            rec = p.band("azcot_wspd_climatology_monthly", "wspd_max")
            rec = np.array([float(rec.sel(month=m)) for m in SEASON])
            shares = wsh.share_gt(np.floor(hi))
            lim, share_def = CAUTION_SHARE, "% of hours with hourly-mean wind above the limit"
            sources = [src("azcot_wspd_climatology_monthly", "wspd_max", "month"),
                       src("azcot_wspd_hour_counts_monthly", "wspd_hour_counts", "month, bin")]
        by_m = month_classes(rec >= hi, shares / 100, lim)
        item.update(verdict=overall(by_m), by_month=by_m,
                    evidence={"record_by_month": dict(zip(months, map(r, rec))),
                              "share_by_month": dict(zip(months, map(r, shares))),
                              "share_definition": share_def,
                              "caution_threshold": f"{lim * 100:g}% ({'of years' if lim == CAUTION_YEARS else 'of hours'})"},
                    source=sources)
        if isinstance(row.notes, str):
            item["notes"] = row.notes
        items.append(item)
    return {
        "title": "Climate-limit verdicts",
        "description": "OK / Caution / No for each environmental design limit in the threshold catalog "
                       "(site_characterization/thresholds.csv): structure snow and snowfall loads, structure wind "
                       "rating, and vehicle type versus snow depth. Equipment, clothing, fuel and other item verdicts "
                       "are not included.",
        "legend": {
            "OK": "The 30-year record never reaches the limit in that month.",
            "CAUTION": "The record reaches the limit, but rarely: in at most 1% of the month's hours "
                       "(MIL-HDBK-310 / AR 70-38 design convention), or, for the single-event snowfall loads, in at "
                       "most 10% of years.",
            "NO": "The limit is reached more often than that.",
            "N/A": "Not meaningful at this cell (e.g. snow load on a glacier cell).",
        },
        "items": items,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Fairbanks, AK")
    ap.add_argument("--lat", type=float, default=64.84)
    ap.add_argument("--lon", type=float, default=-147.72)
    ap.add_argument("--out")
    a = ap.parse_args()

    with xr.open_dataset(PREP / "azcot_surface_type.nc") as st_ds:
        st = st_ds.surface_type.load()
    i, j, dist = nearest(st == 1, a.lat, a.lon)
    with xr.open_dataset(PREP / "azcot_sd_climatology_monthly.nc") as sd_ds:
        si, sj, sdist = nearest(sd_ds.sd_mean.sel(month=1).notnull(), a.lat, a.lon)
        sd_lat, sd_lon = float(sd_ds.lat[si]), float(sd_ds.lon[sj])
    stype = {0: "ocean", 1: "land", 2: "glacier", 3: "perennial_snow"}[int(st.isel(lat=i, lon=j))]
    glat, glon = float(st.lat[i]), float(st.lon[j])
    p = Point(i, j, si, sj)
    p.band("azcot_surface_type", "surface_type")

    t2h = Hist(p, "azcot_t2_hour_counts_monthly", "t2_hour_counts")
    wsh = Hist(p, "azcot_wspd_hour_counts_monthly", "wspd_hour_counts")
    sdh = Hist(p, "azcot_sd_hour_counts_monthly", "sd_hour_counts", "era5land")

    body = {
        "climatology": climatology(p, glat, glon),
        "design_and_zones": design(p, t2h),
        "exceedance": exceedance(p, t2h, wsh, sdh),
        "frostbite": frostbite(p),
        "snowfall_loads": snowfall(p),
        "climate_limit_verdicts": verdicts(p, stype, sdh, wsh),
    }
    coverages = {cid: {"bands": sorted(u["bands"]), "lat": u["lat"], "lon": u["lon"],
                       "example_wcps": wcps(cid, sorted(u["bands"])[0], u["lat"], u["lon"])}
                 for cid, u in sorted(p.used.items())}
    meta = {
        "mock": True,
        "description": "Mock response of a proposed AZCOT point-query API. The values are real (read from the AZCOT "
                       "coverages at the grid cell an API would select); the endpoint, field names and structure are a "
                       "proposal. See mock_api/README.md in the AZCOT repository.",
        "proposed_endpoint": f"/azcot/point/{a.lat:g}/{a.lon:g}",
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "mock_api/make_point_json.py (AZCOT repo)",
        "query": {"name": a.name, "lat": a.lat, "lon": a.lon},
        "grid_cell": {"lat": glat, "lon": glon, "distance_km": r(dist, 1), "surface_type": stype,
                      "grid": "ERA5 0.25 degree (EPSG:4326, cell centre)",
                      "selection": "nearest cell with surface_type = land (seasonal snow)"},
        "snow_depth_grid_cell": {"lat": round(sd_lat, 2), "lon": round(sd_lon, 2), "distance_km": r(sdist, 1),
                                 "grid": "ERA5-Land 0.1 degree", "selection": "nearest cell with snow-depth data"},
        "climatology_period": "1991-2020, October-March (cold season); Feb 29 excluded",
        "periods": {
            "daily": "keys mon_DD (oct_01 ... mar_31, 182 days); each calendar day pools 30 years x 24 hours",
            "monthly": "keys oct, nov, dec, jan, feb, mar",
            "seasonal": "one value for the whole October-March season"},
        "units_system": "US customary: degF, knots, inches, lbf/ft2; shares in %",
        "source_dataset": "AZCOT (ERDC/CRREL TR-26-5, SR-25-2) hourly ERA5, reprocessed by SNAP (preprocess/ in the "
                          "AZCOT repo); snowfall from SNAP's ERA5 holdings",
        "coverage_store": "Rasdaman. Coverage ids are those of the draft recipes in rasdaman/ (not yet ingested); "
                          "values here come from the same ingest-ready NetCDF files.",
        "caveats": [
            "Values describe a 0.25 degree (~28 km) ERA5 grid cell, not the exact site; valleys and ridges can differ "
            "a lot, especially under winter inversions.",
            CLIM_VARS["wind_chill"][3],
            "Storm-total snowfall loads depend on a storm definition we chose (dry gaps <= 12 h); see "
            "snowfall_loads.storm_definition.",
            "Wind is the hourly mean at 10 m; no gusts.",
        ],
        "coverages_used": coverages,
    }
    out = Path(a.out) if a.out else HERE / f"{slug(a.name)}.json"
    out.write_text(json.dumps({"metadata": meta, **body}, indent=1, ensure_ascii=False) + "\n")
    print("wrote", out, f"({out.stat().st_size / 1024:.0f} KB; {len(coverages)} coverages)")


if __name__ == "__main__":
    main()
