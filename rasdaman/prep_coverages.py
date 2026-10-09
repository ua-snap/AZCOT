"""Level 1 (draft): turn the curated AZCOT coverages into Rasdaman-ready NetCDF files plus wcst_import recipes.

Nothing here talks to Rasdaman. It reads preprocess/coverages/*.nc and writes
    <OUT_ROOT>/rasdaman/<coverage_id>.nc      one file per Rasdaman coverage
    rasdaman/recipes/<coverage_id>.json       general_coverage recipe (house style of ua-snap/rasdaman-ingest)
    rasdaman/coverages.csv                    catalog: id, axes, bands, units, size, source file

Rules (see rasdaman/README.md):
  * Every source file becomes one coverage per group of variables sharing the same axes, e.g.
    azcot_wct_stats_daily.nc -> azcot_wct_frequency_daily (axis wct_threshold), azcot_wct_consecutive_daily
    (axis wct_consec_threshold, 2 bands) and azcot_wct_percentile_daily (axis percentile).
  * The CF climatological time axis becomes an irregular Index1D axis holding calendar values, so queries need no
    lookup table: `month` = 1, 2, 3, 10, 11, 12 (monthly files) and `mmdd` = 101 ... 331, 1001 ... 1231 (daily files,
    month * 100 + day; Feb 29 does not exist). Seasonal files are 2-D.
  * Every other non-spatial axis (thresholds, percentiles, histogram bins) keeps its real values, sorted ascending
    (Rasdaman irregular axes must increase), e.g. wct_threshold -100 ... 0.
  * surface_type is split out into its own 2-D coverage, azcot_surface_type (0.25-degree grid only).
  * lat/lon stay on the source grid (EPSG:4326, cell centres, pixelIsPoint). NaN is the float nil value.

Usage: python prep_coverages.py [--only azcot_wct_climatology_daily ...] [--storage /opt/rasdaman-storage/coverage_data/azcot]
                                [--recipes-only]
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "preprocess"))
from config import COVERAGES, out_path  # noqa: E402  (write guard: refuses the read-only source tree)

SKIP = {"crs", "climatology_bounds", "surface_type", "n_hours"}
MONTH_NAME = {1: "jan", 2: "feb", 3: "mar", 10: "oct", 11: "nov", 12: "dec"}
STORAGE = "/opt/rasdaman-storage/coverage_data/azcot"
TILE_BYTES = 4194304


def resolution_of(stem):
    return stem.rsplit("_", 1)[-1]  # daily | monthly | seasonal


def calendar_axis(ds, res):
    """Replace `time` by month or mmdd (sorted ascending); returns (dataset, axis name or None)."""
    if "time" not in ds.dims:
        return ds, None
    month = ds["month"].values.astype(int)
    if res == "daily":
        name, vals = "mmdd", month * 100 + ds["day"].values.astype(int)
        attrs = {"long_name": "calendar day as month*100+day (101 = Jan 1 ... 1231 = Dec 31; no Feb 29)"}
    else:
        name, vals = "month", month
        attrs = {"long_name": "calendar month (1 = January ... 12 = December; Oct-Mar only)"}
    ds = ds.drop_vars([c for c in ("calendar_day", "month", "day", "time") if c in ds.coords or c in ds.variables])
    ds = ds.assign_coords(time=("time", vals.astype(np.int32))).rename({"time": name})
    ds[name].attrs = attrs
    return ds.sortby(name), name


def groups(ds):
    """Data variables grouped by their dims (order kept)."""
    out = {}
    for v, da in ds.data_vars.items():
        if v in SKIP or da.ndim < 2:
            continue
        out.setdefault(da.dims, []).append(v)
    return out


def coverage_id(stem, dims, names):
    extra = [d for d in dims if d not in ("lat", "lon", "time", "month", "mmdd")]
    if not extra:
        return stem  # e.g. azcot_wct_climatology_daily
    prefix = names[0]
    for n in names[1:]:
        while not n.startswith(prefix):
            prefix = prefix[:-1]
    prefix = re.sub(r"_+$", "", prefix)
    return f"azcot_{prefix}_{resolution_of(stem)}"


def tiling(dims, sizes):
    """House default (ALIGNED, ~4 MB tiles) with one entry per axis."""
    return f"ALIGNED [{', '.join('0:*' for _ in dims)}] tile size {TILE_BYTES}"


def axis_entry(name, order, regular):
    if regular:
        return {"min": f"${{netcdf:variable:{name}:min}}", "max": f"${{netcdf:variable:{name}:max}}",
                "resolution": f"${{netcdf:variable:{name}:resolution}}", "gridOrder": order}
    return {"min": f"${{netcdf:variable:{name}:min}}", "max": f"${{netcdf:variable:{name}:max}}",
            "directPositions": f"${{netcdf:variable:{name}}}", "irregular": True, "gridOrder": order}


def encoding_note(ds, axes):
    enc = {}
    for a in axes:
        if a == "month":
            enc[a] = {str(int(v)): MONTH_NAME[int(v)] for v in ds[a].values}
        elif a == "mmdd":
            enc[a] = "month*100+day, e.g. 115 = Jan 15, 1001 = Oct 1"
        else:
            enc[a] = f"{ds[a].attrs.get('long_name', a)} ({ds[a].attrs.get('units', '')})".strip()
    return enc


def recipe(cid, ds, bands, axes, storage, title, summary):
    dims = axes + ["lat", "lon"]
    crs = "@".join([f'OGC/0/Index1D?axis-label="{a}"' for a in axes] + ["EPSG/0/4326"])
    band_list = []
    for b in bands:
        entry = {"name": b, "identifier": b}
        if ds[b].dtype.kind == "f":
            entry["nilValue"] = "nan"
        band_list.append(entry)
    units = {b: ds[b].attrs.get("units", "") for b in bands}
    axes_json = {a: axis_entry(a, i, regular=False) for i, a in enumerate(axes)}
    axes_json["lat"] = axis_entry("lat", len(axes), regular=True)
    axes_json["lon"] = axis_entry("lon", len(axes) + 1, regular=True)
    return {
        "config": {"service_url": "https://localhost/rasdaman/ows", "tmp_directory": "/tmp/", "blocking": True,
                   "mock": False, "automated": True, "track_files": False},
        "input": {"coverage_id": cid, "paths": [f"{storage}/{cid}.nc"]},
        "recipe": {"name": "general_coverage", "options": {
            "wms_import": True, "import_order": "ascending", "tiling": tiling(dims, None),
            "coverage": {
                "crs": crs,
                "metadata": {"type": "xml", "global": {
                    "Title": title, "Summary": summary, "Units": json.dumps(units),
                    "Encoding": json.dumps(encoding_note(ds, axes)),
                    "Source": "AZCOT curated coverages (SNAP, UAF), preprocess/ in the AZCOT repo; ERA5 1991-2020 "
                              "Oct-Mar, Feb 29 excluded"}},
                "slicer": {"type": "netcdf", "pixelIsPoint": True, "bands": band_list, "axes": axes_json}}}},
    }


def prepare(src, storage, recipes_only, only):
    stem = src.stem
    res = resolution_of(stem)
    rows = []
    with xr.open_dataset(src, decode_times=False) as ds0:
        ds, cal = calendar_axis(ds0, res)
        for dims, names in groups(ds).items():
            cid = coverage_id(stem, dims, names)
            if only and cid not in only:
                continue
            extra = [d for d in dims if d not in ("lat", "lon")]
            sub = ds[names]
            for a in extra:
                if a != cal:
                    sub = sub.sortby(a)  # e.g. wct_threshold 0..-100 -> -100..0
            sub = sub.transpose(*extra, "lat", "lon")
            for c in list(sub.coords):
                if c not in dims:
                    sub = sub.drop_vars(c)
            sub.attrs = {k: v for k, v in ds0.attrs.items() if k in ("title", "summary", "source", "references",
                                                                       "institution", "climatology_period")}
            sub.attrs["Conventions"] = "CF-1.8"
            sub.attrs["comment"] = f"Rasdaman-ready copy of {src.name} (variables {', '.join(names)}); see rasdaman/README.md"
            dest = out_path("rasdaman", f"{cid}.nc")
            if not recipes_only:
                enc = {v: {"zlib": True, "complevel": 1} for v in names}
                for v in names:
                    if sub[v].dtype.kind == "f":
                        enc[v]["_FillValue"] = np.float32(np.nan)
                for c in sub.coords:
                    enc[c] = {"_FillValue": None}
                sub.to_netcdf(dest, encoding=enc)
            title = ds0.attrs.get("title", cid).replace("AZCOT curated cold-season climatology coverages: ", "AZCOT ")
            rec = recipe(cid, sub, names, extra, storage, title, ds0.attrs.get("summary", ""))
            (HERE / "recipes").mkdir(exist_ok=True)
            (HERE / "recipes" / f"{cid}.json").write_text(json.dumps(rec, indent=2) + "\n")
            nbytes = sum(int(np.prod([sub.sizes[d] for d in sub[v].dims])) * sub[v].dtype.itemsize for v in names)
            rows.append({"coverage_id": cid, "axes": " ".join(extra + ["lat", "lon"]),
                         "shape": " x ".join(str(sub.sizes[d]) for d in extra + ["lat", "lon"]),
                         "bands": " ".join(names), "units": " ".join(sub[v].attrs.get("units", "-") for v in names),
                         "uncompressed_MB": round(nbytes / 2**20), "source": src.name})
            print(f"{cid:42s} {rows[-1]['shape']:28s} {rows[-1]['bands']}", flush=True)
        if "surface_type" in ds0 and (not only or "azcot_surface_type" in only) and stem == "azcot_wct_climatology_seasonal":
            st = ds0[["surface_type"]].copy()
            st.attrs = {"title": "AZCOT surface type (ocean / land / glacier / perennial snow)", "Conventions": "CF-1.8"}
            if not recipes_only:
                st.to_netcdf(out_path("rasdaman", "azcot_surface_type.nc"),
                             encoding={"surface_type": {"zlib": True}, "lat": {"_FillValue": None},
                                       "lon": {"_FillValue": None}})
            rec = recipe("azcot_surface_type", st, ["surface_type"], [], storage, st.attrs["title"],
                         ds0["surface_type"].attrs.get("comment", ""))
            enc = json.loads(rec["recipe"]["options"]["coverage"]["metadata"]["global"]["Encoding"])
            enc["surface_type"] = {"0": "ocean", "1": "land", "2": "glacier", "3": "perennial_snow"}
            rec["recipe"]["options"]["coverage"]["metadata"]["global"]["Encoding"] = json.dumps(enc)
            (HERE / "recipes" / "azcot_surface_type.json").write_text(json.dumps(rec, indent=2) + "\n")
            rows.append({"coverage_id": "azcot_surface_type", "axes": "lat lon", "shape": "121 x 1440",
                         "bands": "surface_type", "units": "flag", "uncompressed_MB": 0, "source": src.name})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", help="coverage ids to (re)build")
    ap.add_argument("--storage", default=STORAGE, help="directory the Rasdaman server reads the files from")
    ap.add_argument("--recipes-only", action="store_true", help="write recipes and catalog, not the NetCDF files")
    args = ap.parse_args()
    rows = []
    for src in sorted(COVERAGES.glob("azcot_*.nc")):
        rows += prepare(src, args.storage, args.recipes_only, set(args.only or []))
    if not args.only:
        with open(HERE / "coverages.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: r["coverage_id"]))
        print(f"{len(rows)} coverages; catalog rasdaman/coverages.csv", flush=True)


if __name__ == "__main__":
    main()
