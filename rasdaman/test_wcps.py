"""Level 1 acceptance queries for the AZCOT Rasdaman coverages.

Each test is a WCPS query plus the same calculation done locally on the prepared NetCDF file, so the expected answer is
known before anything is ingested. After an ingest, run against the server and every answer must match.

    python test_wcps.py --local                     # expected answers only (no server)
    python test_wcps.py --endpoint https://zeus.snap.uaf.edu/rasdaman/ows
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "preprocess"))
from config import OUT_ROOT  # noqa: E402

PREP = OUT_ROOT / "rasdaman"
FAI = (64.75, -147.75)  # Fairbanks grid cell
BOX = {"lat": (64.0, 66.0), "lon": (-150.0, -145.0)}  # interior Alaska around Fairbanks
JAN_HOURS = 31 * 720


def open_prep(cid):
    return xr.open_dataset(PREP / f"{cid}.nc")


def local_point_t2_min():
    with open_prep("azcot_t2_climatology_daily") as ds:
        return float(ds.t2_min.sel(mmdd=115, lat=FAI[0], lon=FAI[1]))


def local_area_mean_freq():
    with open_prep("azcot_wct_frequency_monthly") as ds:
        a = ds.wct_frequency.sel(month=1, wct_threshold=-40.0, lat=slice(*BOX["lat"]), lon=slice(*BOX["lon"]))
        return float(np.nanmean(a.values))


def local_share_below_limit(limit=-53):
    with open_prep("azcot_t2_hour_counts_monthly") as ds:
        c = ds.t2_hour_counts.sel(month=1, bin=slice(None, limit), lat=FAI[0], lon=FAI[1])
        return float(c.sum()) / JAN_HOURS * 100


def local_series():
    with open_prep("azcot_wct_climatology_daily") as ds:
        return [round(float(v), 3) for v in ds.wct_mean.sel(lat=FAI[0], lon=FAI[1]).values[:5]]


def local_surface_type():
    with open_prep("azcot_surface_type") as ds:
        return int(ds.surface_type.sel(lat=76.5, lon=-40.0))  # central Greenland ice sheet -> 2 (glacier)


TESTS = [
    ("point: record-low 2 m air temperature at Fairbanks on Jan 15 (degF)",
     f'for $c in (azcot_t2_climatology_daily) return $c.t2_min[mmdd(115), lat({FAI[0]}), lon({FAI[1]})]',
     local_point_t2_min),
    ("area: mean % of January hours with wind chill <= -40 degF, 64-66N 150-145W",
     'for $c in (azcot_wct_frequency_monthly) return avg($c.wct_frequency[month(1), wct_threshold(-40), '
     f'lat({BOX["lat"][0]}:{BOX["lat"][1]}), lon({BOX["lon"][0]}:{BOX["lon"][1]})])',
     local_area_mean_freq),
    ("limit: % of January hours at Fairbanks at or below -53 degF (any equipment rating works)",
     'for $c in (azcot_t2_hour_counts_monthly) return '
     f'(sum($c.t2_hour_counts[month(1), bin(-120:-53), lat({FAI[0]}), lon({FAI[1]})]) / {JAN_HOURS}) * 100',
     local_share_below_limit),
    ("series: first 5 days (Jan 1-5) of mean wind chill at Fairbanks (degF)",
     f'for $c in (azcot_wct_climatology_daily) return encode($c.wct_mean[mmdd(101:105), lat({FAI[0]}), '
     f'lon({FAI[1]})], "application/json")',
     local_series),
    ("flag: surface type in central Greenland (2 = glacier)",
     'for $c in (azcot_surface_type) return $c.surface_type[lat(76.5), lon(-40)]',
     local_surface_type),
]


def run_wcps(endpoint, query):
    url = f"{endpoint}?" + urllib.parse.urlencode({"service": "WCS", "version": "2.0.1",
                                                   "request": "ProcessCoverages", "query": query})
    with urllib.request.urlopen(url, timeout=120) as r:
        text = r.read().decode().strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return float(text)


def close(a, b):
    a, b = np.atleast_1d(np.asarray(a, float)), np.atleast_1d(np.asarray(b, float))
    return a.shape == b.shape and np.allclose(a, b, rtol=1e-4, atol=1e-3)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--local", action="store_true")
    g.add_argument("--endpoint")
    args = ap.parse_args()
    ok = True
    for title, query, local in TESTS:
        want = local()
        print(f"- {title}\n  WCPS: {query}\n  expected: {want}")
        if args.endpoint:
            got = run_wcps(args.endpoint, query)
            passed = close(got, want)
            ok &= passed
            print(f"  server:   {got}  -> {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
