# AZCOT in Rasdaman (Level 1, draft)

This folder turns the curated AZCOT coverages ([preprocess/](../preprocess/README.md)) into Rasdaman coverages. **Nothing has been ingested.** The recipes follow the house style of [ua-snap/rasdaman-ingest](https://github.com/ua-snap/rasdaman-ingest) (`general_coverage`, NetCDF slicer, EPSG:4326, irregular `Index1D` axes) and can be copied there when we decide to ingest.

| File | What it is |
|---|---|
| `prep_coverages.py` | Writes one Rasdaman-ready NetCDF per coverage to `/beegfs/CMIP6/jdpaul3/azcot_preprocess/rasdaman/`, plus `recipes/*.json` and `coverages.csv` |
| `recipes/<coverage_id>.json` | `wcst_import.sh` recipe per coverage |
| `coverages.csv` | Catalog: coverage id, axes, shape, bands, units, uncompressed size, source file |
| `test_wcps.py` | Acceptance queries with their expected answers, computed locally from the prepared files |

## Design

**One coverage per group of variables that share axes.** Rasdaman bands must share all axes, so a source file whose variables have different extra axes is split. For example, `azcot_wct_stats_daily.nc` becomes three coverages:
- `azcot_wct_frequency_daily`, on axis `wct_threshold`;
- `azcot_wct_consecutive_daily`, with 2 bands, on axis `wct_consec_threshold`;
- `azcot_wct_percentile_daily`, on axis `percentile`.

Climatology files keep their name, e.g. `azcot_t2_climatology_daily`, with bands `t2_min`, `t2_mean` and `t2_max`.

**Calendar axes hold real calendar values, so queries need no lookup table.** The CF climatological `time` axis of the source files uses nominal dates in a fake 2001–02 season, which reads badly in a query. It becomes an irregular `Index1D` axis instead:

| Resolution | Axis | Values | Example |
|---|---|---|---|
| daily | `mmdd` | month × 100 + day: 101 … 331, 1001 … 1231 (no Feb 29) | `mmdd(115)` = Jan 15 |
| monthly | `month` | 1, 2, 3, 10, 11, 12 | `month(1)` = January |
| seasonal | — | 2-D (lat, lon) | |

**Every other non-spatial axis keeps its real values, sorted ascending**, because Rasdaman irregular axes must increase. Examples: `wct_threshold` −100 … 0, `sl_threshold` 0 … 50, `percentile`, and histogram `bin` (°F, kn, in, minutes or lb/ft² as the coverage says). So `wct_threshold(-40)` and `bin(-120:-53)` work directly.

**Surface type is its own coverage** (`azcot_surface_type`, 2-D, int8: 0 ocean, 1 land, 2 glacier, 3 perennial snow). Its flag meanings are in the coverage metadata.

**Grid:** EPSG:4326 cell centres (`pixelIsPoint`), lat 60–90 ascending, lon −180 … 179.75. The snow-depth coverages are on the 0.1° ERA5-Land grid instead. Float bands use NaN as the nil value. Histogram counts are int16 with no nil value (0 = no hours).

**Metadata** (`global` block): `Title`, `Summary`, `Units` (JSON, band → units), `Encoding` (JSON, axis → meaning; `month` labels), `Source`.

**Tiling:** the house default, `ALIGNED [0:*, …] tile size 4194304`. The likely first app use is point queries (one cell, every month, threshold and bin). For that, tiles that are small in lat/lon and span the whole non-spatial extent would be faster, e.g. `REGULAR [0:5, 0:200, 0:15, 0:15]` for `azcot_t2_hour_counts_monthly` (6 × 201 × 16 × 16 × 2 bytes ≈ 0.6 MB). This is untested; benchmark before changing.

## Coverages

[`coverages.csv`](coverages.csv) lists every coverage. By family:

| Family | Coverages | Axes |
|---|---|---|
| Climatology (true min / mean / max) | `azcot_{wct,sl,t2,wspd,sd}_climatology_{daily,monthly,seasonal}` | (`mmdd` or `month`), lat, lon |
| Wind chill and snow load statistics (from `Metrics`) | `azcot_wct_{frequency,consecutive}_{daily,monthly,seasonal}`, `azcot_wct_percentile_daily`, `azcot_sl_frequency_{daily,monthly,seasonal}`, `azcot_sl_percentile_daily` | + threshold or percentile |
| Hourly-value histograms | `azcot_{t2,wspd,sd}_hour_counts_monthly` | month, `bin`, lat, lon |
| Frostbite (Level 2) | `azcot_frostbite_{daily,monthly,seasonal}`, `azcot_frostbite_hour_counts_monthly` | (`mmdd`/`month`; histogram `bin` in minutes) |
| Snowfall loads (Level 2) | `azcot_snowfall_{daily,monthly,seasonal}`, `azcot_sf24_day_counts_monthly`, `azcot_storm_counts_monthly` | (`mmdd`/`month`; histogram `sf24_bin` / `storm_bin` in lb/ft²) |
| Flag | `azcot_surface_type` | lat, lon |

**Size.** Rasdaman stores tiles uncompressed by default. The prepared NetCDF files are compressed, but the uncompressed size is the sum of `uncompressed_MB` in `coverages.csv`. That is **17.3 GB for all 39 coverages**: 15.3 GB for Level 1 and 2.0 GB for the Level 2 frostbite and snowfall coverages. This is more than the 4–8 GB in the scoping estimate. The prepared NetCDF files take 3.6 GB on disk. The largest are `azcot_wct_consecutive_daily` (3.9 GB), `azcot_wct_frequency_daily` (2.5 GB) and `azcot_sd_climatology_daily` (2.3 GB). The daily statistics coverages could be left out if space matters, since monthly and seasonal versions exist.

## How to ingest (when we decide to)

```bash
# 1. Build the Rasdaman-ready files and recipes (compute node: the daily stats need ~10 GB RAM)
PY=~/micromamba/envs/azcot-preprocess/bin/python
$PY rasdaman/prep_coverages.py            # all coverages; --only <id> ... for some; --recipes-only to skip the data

# 2. Copy the files to the server's storage directory (the recipes point at
#    /opt/rasdaman-storage/coverage_data/azcot/<coverage_id>.nc; change it with --storage)
rsync -av /beegfs/CMIP6/jdpaul3/azcot_preprocess/rasdaman/ <server>:/opt/rasdaman-storage/coverage_data/azcot/

# 3. On the server, one recipe at a time (as for the other rasdaman-ingest recipes)
wcst_import.sh recipes/azcot_t2_climatology_daily.json

# 4. From anywhere: compare the live coverages with the expected answers
$PY rasdaman/test_wcps.py --endpoint https://zeus.snap.uaf.edu/rasdaman/ows
```

To move this into `rasdaman-ingest`, copy `recipes/` to a new folder there, e.g. `azcot/`. It could also get a Prefect flow in `prefect/rasdaman/` like the existing ones (`clone_github_repository` + `run_ingest`). No WMS styles are defined yet.

## Example WCPS queries

These are the queries in `test_wcps.py`. Expected answers were computed from the prepared files (see `python test_wcps.py --local`):

| Question | WCPS | Expected |
|---|---|---|
| Record-low air temperature at Fairbanks on Jan 15 | `for $c in (azcot_t2_climatology_daily) return $c.t2_min[mmdd(115), lat(64.75), lon(-147.75)]` | −47.77 °F |
| Mean % of January hours with wind chill ≤ −40 °F, 64–66 °N, 150–145 °W | `for $c in (azcot_wct_frequency_monthly) return avg($c.wct_frequency[month(1), wct_threshold(-40), lat(64.0:66.0), lon(-150.0:-145.0)])` | 20.56% |
| % of January hours at Fairbanks at or below an equipment rating of −53 °F | `for $c in (azcot_t2_hour_counts_monthly) return (sum($c.t2_hour_counts[month(1), bin(-120:-53), lat(64.75), lon(-147.75)]) / 22320) * 100` | 0.049% |
| Mean wind chill at Fairbanks, Jan 1–5 | `for $c in (azcot_wct_climatology_daily) return encode($c.wct_mean[mmdd(101:105), lat(64.75), lon(-147.75)], "application/json")` | −13.7, −12.7, −15.4, −16.0, −17.9 °F |
| Surface type in central Greenland | `for $c in (azcot_surface_type) return $c.surface_type[lat(76.5), lon(-40)]` | 2 (glacier) |

The third query is the core of the "pick a point, check an item" use: any limit, to the nearest degree, in one request. 22,320 is January's hour count (31 days × 720 hours); the monthly histogram coverages also carry it, as `n_hours` in the source files.

## Open questions for the Rasdaman admins

- Whether irregular `Index1D` axes with float positions (e.g. `wct_threshold` −100.0 … 0.0) and with gaps (`month` 1, 2, 3, 10, 11, 12) slice as expected; `test_wcps.py` checks both.
- Whether `nilValue: "nan"` works for these float bands, as it does for `cmip6_monthly_cf_wms`.
- Tiling for point queries (see above), and whether to ingest the large daily statistics at all.
