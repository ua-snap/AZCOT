"""Summary statistics for EDA.md: land-wide numbers vs. TR-26-5, and a per-location table.

Writes eda/tables/report_comparison.csv and eda/tables/locations.csv (and prints markdown).
"""
import numpy as np
import pandas as pd

from azcot import EDA, LOCATIONS, load_cube, load_masks, nearest_land_cell

TABLES = EDA / "tables"


def land_mean(da, mask, weighted=False):
    da = da.where(mask)
    if weighted:
        w = np.cos(np.radians(da.g0_lat_0))
        return float(da.weighted(w).mean(["g0_lat_0", "g0_lon_1"]))
    return float(da.mean())


def main():
    TABLES.mkdir(exist_ok=True)
    m = load_masks()
    wct = load_cube("wct").load()
    sl = load_cube("sl").load()
    land, land_ng = m.land, m.land & ~m.glacier
    # Exclude Feb 29 (8 leap years only; min_WCT bug) from season aggregates.
    keep = [d for d in wct.day.values if d != "feb_29"]
    wct, sl = wct.sel(day=keep), sl.sel(day=keep)

    rows = []

    def add(q, value_unw, value_w, report, note=""):
        rows.append({"quantity": q, "this EDA (pixel mean)": round(value_unw, 2),
                     "this EDA (area-weighted)": round(value_w, 2), "TR-26-5": report, "note": note})

    season_wct = wct.averageTemp.mean("day")
    add("Average Oct–Mar wind chill over land (°F)", land_mean(season_wct, land), land_mean(season_wct, land, True),
        -23.9, "averageTemp, mean of daily files")
    f65 = wct["frequency_-65"].mean("day")
    add("Share of hours with WCT ≤ −65 °F, land (%)", land_mean(f65, land), land_mean(f65, land, True), 7.66)
    p1min = wct.percentile_1.min("day")
    add("Coldest daily 1st-percentile WCT, land avg (°F)", land_mean(p1min, land), land_mean(p1min, land, True),
        -86.7, "report value is the true record low; Metrics have no true min for WCT")
    mwmin = wct.min_WCT.min("day")
    add("Coldest daily min_WCT (avg of yearly lows), land avg (°F)", land_mean(mwmin, land),
        land_mean(mwmin, land, True), -86.7, "not comparable: min_WCT is a mean of annual minima")
    season_sl = sl.averageSL.mean("day")
    add("Average Oct–Mar snow load, non-glacier land (lb/ft²)", land_mean(season_sl, land_ng),
        land_mean(season_sl, land_ng, True), 13.8)
    rec = sl.max_SL.max("day")
    add("Highest recorded snow load, non-glacier land avg (lb/ft²)", land_mean(rec, land_ng),
        land_mean(rec, land_ng, True), 42.9)
    typ = sl.averageSL.max("day")
    for thr in (10, 20, 25, 48):
        add(f"Non-glacier land where typical peak SL < {thr} lb/ft² (%)", 100 * land_mean(typ < thr, land_ng),
            100 * land_mean(typ < thr, land_ng, True), "")
        add(f"Non-glacier land where record SL < {thr} lb/ft² (%)", 100 * land_mean(rec < thr, land_ng),
            100 * land_mean(rec < thr, land_ng, True), "")
    for thr in (-40, -65):
        never = wct[f"frequency_{thr}"].max("day") == 0
        add(f"Land where WCT never reached ≤ {thr} °F in 30 yr (%)", 100 * land_mean(never, land),
            100 * land_mean(never, land, True), "")
    comp = pd.DataFrame(rows)
    comp.to_csv(TABLES / "report_comparison.csv", index=False)
    print(comp.to_markdown(index=False))

    loc = []
    jan = [d for d in keep if d.startswith("jan")]
    for name, lat, lon in LOCATIONS:
        i, j = nearest_land_cell(lat, lon, m.land)
        w, s = wct.isel(g0_lat_0=i, g0_lon_1=j), sl.isel(g0_lat_0=i, g0_lon_1=j)
        first25 = np.flatnonzero(s.averageSL.values >= 25)
        loc.append({
            "location": name,
            "grid cell": f"{float(w.g0_lat_0):.2f}, {float(w.g0_lon_1):.2f}",
            "Jan avg WCT (°F)": round(float(w.averageTemp.sel(day=jan).mean()), 1),
            "Jan 1st-pct WCT (°F)": round(float(w.percentile_1.sel(day=jan).mean()), 1),
            "season % hrs ≤ −40": round(float(w["frequency_-40"].mean()), 1),
            "season % hrs ≤ −65": round(float(w["frequency_-65"].mean()), 2),
            "Mar 31 avg SL (lb/ft²)": round(float(s.averageSL[-1]), 1),
            "peak avg SL": round(float(s.averageSL.max()), 1),
            "record SL": round(float(s.max_SL.max()), 1),
            "avg SL ≥ 25 from": s.day.values[first25[0]].replace("_", " ") if first25.size else "never",
            "glacier cell": bool(m.glacier[i, j]),
        })
    loc = pd.DataFrame(loc)
    loc.to_csv(TABLES / "locations.csv", index=False)
    print()
    print(loc.to_markdown(index=False))


if __name__ == "__main__":
    main()
