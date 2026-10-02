# AZCOT preprocessing: curated wind chill and snow load coverages

This pipeline condenses the AZCOT ERA5 cold-season data into a small set of curated NetCDF coverages for **wind chill temperature (WCT)** and **snow load (SL)**, ready for mapping and analysis:

- **Climatology coverages** (daily, monthly, seasonal) with a true **min of min**, **mean of mean**, and **max of max** for every grid cell, recomputed from the raw hourly data.
- **Stats coverages** (daily, monthly, seasonal) with threshold frequencies, consecutive-hour persistence, and percentiles, taken from `disk1/Metrics`.
- A **`surface_type` flag** in every file (ocean / land / glacier / perennial snow), so glaciers can be symbolized on their own instead of showing up as missing data.

It fixes the two problems the EDA ([eda/EDA.md](../eda/EDA.md)) found in `disk1/Metrics`:

1. **Feb 29 is dropped.** It pools only 8 leap years, and its `min_WCT` is computed incorrectly. Every coverage uses the 182-day Oct 1 – Mar 31 calendar without Feb 29.
2. **True extremes replace `min_WCT`.** `Metrics` `min_WCT` is the *mean of the 30 annual minima*, not the record low, and `Metrics` has no WCT maximum or SL minimum. The pipeline recomputes min, mean, and max from all 720 hourly values (30 years × 24 h) of each calendar day.

Output root: **`/beegfs/CMIP6/jdpaul3/azcot_preprocess`**

## Outputs

`coverages/` (all on the same 0.25° grid: 1440 × 121, 60–90 °N, lat ascending, lon −180…179.75, EPSG:4326):

| File | Time axis | Variables |
|---|---|---|
| `azcot_wct_climatology_daily.nc` | 182 days | `wct_min`, `wct_mean`, `wct_max` (°F) |
| `azcot_wct_climatology_monthly.nc` | 6 months | same |
| `azcot_wct_climatology_seasonal.nc` | none (one Oct–Mar field) | same |
| `azcot_sl_climatology_{daily,monthly,seasonal}.nc` | as above | `sl_min`, `sl_mean`, `sl_max` (lb/ft²) |
| `azcot_wct_stats_daily.nc` | 182 days | `wct_frequency` (% hours ≤ T, T = 0…−100 °F), `wct_consecutive`, `wct_consecutive_no_ones` (hours, T = 0…−75 °F), `wct_percentile` (P = 1, 5, 10, 15, 20, 25, 50) |
| `azcot_wct_stats_{monthly,seasonal}.nc` | 6 months / none | `wct_frequency`, `wct_consecutive`, `wct_consecutive_no_ones` |
| `azcot_sl_stats_daily.nc` | 182 days | `sl_frequency` (% hours ≥ T, T = 0…50 lb/ft²), `sl_percentile` (P = 50, 75, 80, 85, 90, 95, 99) |
| `azcot_sl_stats_{monthly,seasonal}.nc` | 6 months / none | `sl_frequency` |

Every file also has `surface_type` and a `crs` grid-mapping variable. Thresholds and percentiles are coordinate dimensions (`wct_threshold`, `wct_consec_threshold`, `sl_threshold`, `percentile`) rather than one variable per threshold.

`intermediate/` holds `hourly_reduce/{wct,sl}/{mon}_{DD}.nc` (step 1: per-day min / mean / max, plus the mean of annual minima and maxima kept for validation) and `surface_type.nc` (step 2, with the diagnostic fields the rule uses). `validation/validation_report.md` is written by step 5. `logs/` holds the SLURM logs.

### What the statistics mean

| Resolution | `*_min` | `*_mean` | `*_max` |
|---|---|---|---|
| daily | lowest of the 720 hourly values for that calendar day (1991–2020) | mean of the 720 | highest of the 720 |
| monthly | min of the daily mins | mean of the daily means (= mean of all hours, since every day has 720) | max of the daily maxes |
| seasonal | min over all 182 days | mean over all 182 days | max over all 182 days |

So `wct_min` is the **lowest hourly wind chill recorded in 30 years**, and `sl_max` is the **highest hourly snow load recorded**. These match the Atlas "Lowest/Highest Recorded" maps and the TR-26-5 tables.

Monthly and seasonal **frequency** and **consecutive** stats are means of the daily values. That is exact for frequency, because every day has 720 hours, and it matches how the Atlas aggregated consecutive. **Percentiles exist only at daily resolution:** daily percentiles can't be combined into a correct monthly percentile (ERDC/CRREL SR-25-2 §3.7 says the same). `wct_consecutive` counts years with no qualifying run as 0, so it mixes how often spells occur with how long they last (see the EDA).

### Time axis

Daily and monthly files use a CF climatological time axis. `time` holds nominal dates in a non-leap reference season (2001-10-01 … 2002-03-31) so the files sort in season order, and `climatology_bounds` gives the true span (each calendar day or month, 1991–2020). Daily files also carry `calendar_day` (e.g. `jan_15`), `month`, and `day` coordinates. Seasonal files have no time dimension.

## Glaciers and `surface_type`

ERA5 has no separate glacier model. A grid box more than 50% ice-covered is given a constant snow mass of **10 m water equivalent**:

> "The current model formulation (as in ERA5) does not have an independent treatment of glaciers. Grid points with glaciers are assigned with a constant snow mass of 10 m. A threshold of 50 % of a grid box covered by ice is used, below which the snow depth keeps the value computed by the snow scheme of the land model. Values above the threshold assign a snow water equivalent value of 10 m."
> — Muñoz-Sabater, J., et al. (2021), ERA5-Land: a state-of-the-art global reanalysis dataset for land applications, *Earth Syst. Sci. Data* 13, 4349–4383, §2.1, [doi:10.5194/essd-13-4349-2021](https://doi.org/10.5194/essd-13-4349-2021)

AZCOT computes snow load as SL = SWE[in] × 5.2 lb/ft² (TR-26-5 eq. 4), so 10 m w.e. = 393.7 in × 5.2 = **2047.24 lb/ft²**. That is the value seen across Greenland and the ice caps, and the raw SWE GRIBs top out at exactly 10.0 m. (The EDA's 2047.25 is the same value after float32 rounding.) It is a model constant, not a snow load.

| `surface_type` | Meaning | Rule | SL variables |
|---|---|---|---|
| 0 ocean | water | not land in ERA5-Land (snow depth NaN in `disk1/Metrics/daily_SD_stats`, nearest 0.1° → 0.25° cell) **and** no snow in any hour | NaN |
| 1 land | seasonal snow | ERA5-Land land **or** snow in any hour, and not 2 or 3. ERA5 only carries snow on its own land points; about 5,700 coastal cells have ERA5 snow (median peak 17 lb/ft²) but fall on water in the finer ERA5-Land mask, and would otherwise be lost | valid |
| 2 glacier | held at the ERA5 10 m w.e. constant | lowest hourly SL across the whole season ≥ 99.9% of 2047.24 | NaN |
| 3 perennial snow | land whose snowpack never melts out, so it piles up toward the cap | not glacier, and the lowest hourly SL on Oct 1 in any of the 30 years ≥ 50 lb/ft² | NaN |

Cell counts (of 174,240): ocean 106,769 · land 53,233 · glacier 10,042 · perennial snow 4,196.

The data supports both rules clearly. Exactly 10,042 cells sit at the cap in *every* hour of the season, and no cell reaches it only part of the time. Among the other cells, the least-snowy Oct 1 hour is bimodal: 4,266 cells are ≥ 10 lb/ft² and 4,196 are ≥ 50, many of them 500–2,000 lb/ft². These form a thin ring around each glacier: grid boxes under the 50% ice threshold, where ERA5's snow scheme keeps accumulating snow from year to year instead of applying the 10 m constant.

Map products should symbolize classes 2 and 3 from `surface_type` (for example with a hatched "glacier / permanent snow" class) instead of showing the NaN snow-load cells as no-data. WCT is **not** masked, since wind chill over ice and ocean is physically meaningful. Use `surface_type` there too if you want land-only maps.

## How to run

```bash
# once: create the environment
micromamba create -f preprocess/environment.yml -p ~/micromamba/envs/azcot-preprocess

# submit the whole pipeline to SLURM (step 1, then steps 2-5 after step 1 succeeds)
bash preprocess/run_all.sh
```

Or run the steps one at a time from `preprocess/` (`PY=~/micromamba/envs/azcot-preprocess/bin/python`):

| Step | Command | What it does | Runtime |
|---|---|---|---|
| 1 | `sbatch step1_reduce_hourly.slurm` | 2 × 182 × 720 raw hourly files → per-day min/mean/max (24 cores) | 8 min |
| 2 | `$PY step2_surface_type.py` | `surface_type` flag | < 1 min |
| 3 | `$PY step3_climatology.py` | 6 climatology coverages | ~1 min |
| 4 | `$PY step4_stats.py` | 6 stats coverages (peaks at ~16 GB RAM, so use a compute node) | ~1.5 min |
| 5 | `$PY step5_validate.py` | checks, `validation/validation_report.md`; exits non-zero on failure | ~1 min |

`sbatch steps2to5.slurm` runs steps 2–5 together. Step 1 is **resumable**: each day is written atomically, and finished days are skipped on re-run, so just re-submit after an interruption. Steps 2–5 overwrite their outputs. Set `AZCOT_PRE_OUT=/some/dir` to write somewhere else (e.g. for a test run: `AZCOT_PRE_OUT=/tmp/test $PY step1_reduce_hourly.py --days jan_15`).

Code layout: `config.py` (paths, calendar, constants, `out_path()` write guard), `cf.py` (CF metadata, CRS, time axis), and one script per step.

## Source data safety

The pipeline only *reads* `/beegfs/SNAP/rltorgerson/AZCOT`:

- Everything under `disk1/` and `disk2/` is owned by `rltorgerson` and is read-only to other accounts (`r-xr-xr-x` / `r-x` for the `snap` group), so the operating system blocks writes to the data. **Exception:** the top-level `AZCOT/` directory itself is group-writable (`drwxrws---`, group `snap`), so members of `snap` could rename or remove `disk1`/`disk2` themselves. This pipeline never writes there, but the owner may want to run `chmod g-w` on it. Step 5 reports this as a warning.
- Raw NetCDF is opened with xarray (read-only by default) and GRIB with `open(path, "rb")` + ecCodes. No index or sidecar files are written next to the GRIBs. The Metrics and Atlas files are opened read-only.
- Every output path goes through `config.out_path()`, which raises an error for any path inside the source tree.
- Step 5 re-checks write permissions and confirms that none of the Metrics files used, or a random sample of 2,000 raw files, were modified after the pipeline started.

No copy of the 1.4 TB source is needed.

## Validation

Step 5 checks all 182 days and every grid cell (`validation/validation_report.md`). The latest run passes:

| Check | Max difference |
|---|---:|
| `wct_mean` (daily) vs `Metrics` `averageTemp` | 1.4e-4 °F |
| our mean of yearly minimums vs `Metrics` `min_WCT` (confirms how `min_WCT` was built) | 3.1e-5 °F |
| `wct_min` (daily) vs Atlas "Lowest Recorded" GeoTIFFs, all land cells | 0 (identical) |
| `wct_min` ≤ `Metrics` `percentile_1` | 0 violations |
| `sl_mean` / `sl_max` (daily) vs `Metrics` `averageSL` / `max_SL` | ≤ 1.3e-5 relative (float32 round-off in `Metrics`; ≤ 3.5e-4 lb/ft² on land cells) |

The seasonal coverages also reproduce the TR-26-5 land-wide numbers (unweighted means over ERA5-Land cells): average WCT −24.04 °F (report −23.9), average lowest WCT −86.73 °F (−86.7), average snow load 13.81 lb/ft² (13.8), average highest snow load 42.94 lb/ft² (42.9).

## Using the coverages

- **Python:** `xr.open_dataset(".../azcot_sl_climatology_monthly.nc")`. Select a threshold with `.sel(wct_threshold=-40)`.
- **Glacier symbology:** add `surface_type` as a second layer, make classes 2 (glacier) and 3 (perennial snow) visible with their own symbols, and draw it above the snow-load layer, whose NaN cells show through as no-data.

Output files are created `-rw-------` (owner only). Run `chmod -R g+rX /beegfs/CMIP6/jdpaul3/azcot_preprocess` to share them with the `cmip6` group.

## Inputs used

| Input | Used for |
|---|---|
| `disk1/data/{mon}/{DD}/YYMMDDHH.WCT.nc` | WCT min/mean/max (variable `WCT`, °F, lat stored 90 → 60) |
| `disk1/data/{mon}/{DD}/YYMMDDHH.SWE.grib` | SL min/mean/max (ERA5 `sd`, m w.e. → lb/ft²; GRIB date checked against the file name) |
| `disk1/Metrics/daily_{WCT,SL}_stats/*.nc` | stats coverages; validation |
| `disk1/Metrics/daily_SD_stats/jan_15_SD_stats.nc` | ERA5-Land land mask |
| `disk2/Atlas/{mon}/Daily/{DD}/WCT/Extreme/*_WCT_min.tif` | validation of `wct_min` |
