# AZCOT preprocessing: curated cold-season coverages

This pipeline condenses the AZCOT ERA5 cold-season data into a small set of curated NetCDF coverages for **wind chill temperature (WCT)** and **snow load (SL)** (steps 1–5), plus **air temperature (2T)**, **10 m wind speed (WSPD)** and **snow depth (SD)** (steps 6–8), and the Level 2 products **frostbite danger classes** and **24-hour / storm snowfall loads** (steps 9–12; snowfall from SNAP's ERA5 holdings), ready for mapping and analysis:

- **Climatology coverages** (daily, monthly, seasonal) with a true **min of min**, **mean of mean**, and **max of max** for every grid cell, recomputed from the raw hourly data.
- **Stats coverages** (daily, monthly, seasonal) with threshold frequencies, consecutive-hour persistence, and percentiles, taken from `disk1/Metrics`.
- A **`surface_type` flag** in every file (ocean / land / glacier / perennial snow), so glaciers can be symbolized on their own instead of showing up as missing data.

It fixes the two problems the EDA ([eda/EDA.md](../eda/EDA.md)) found in `disk1/Metrics`:

1. **Feb 29 is dropped.** It pools only 8 leap years, and its `min_WCT` is computed incorrectly. Every coverage uses the 182-day Oct 1 – Mar 31 calendar without Feb 29.
2. **True extremes replace `min_WCT`.** `Metrics` `min_WCT` is the *mean of the 30 annual minima*, not the record low, and `Metrics` has no WCT maximum or SL minimum. The pipeline recomputes min, mean, and max from all 720 hourly values (30 years × 24 h) of each calendar day.

**Wind chill is AZCOT's, computed from skin temperature.** The WCT coverages take `WCT.nc` as it is. That turns out to be the NWS formula applied to ERA5 **skin** temperature (SKT), not the 2 m air temperature that TR-26-5 eq. 3 names; over land in January it runs about 3.5 °F colder (see [AZCOT_DATA_ISSUES.md](../AZCOT_DATA_ISSUES.md), issue 10). The frostbite classes (step 9) use 2 m air temperature, as TR-26-5 Eq. 5 specifies.

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
| `azcot_t2_climatology_{daily,monthly,seasonal}.nc` | as above | `t2_min`, `t2_mean`, `t2_max` (°F); monthly/seasonal also `t2_freeze_thaw_days` |
| `azcot_wspd_climatology_{daily,monthly,seasonal}.nc` | as above | `wspd_min`, `wspd_mean`, `wspd_max` (knots, hourly mean at 10 m; no gusts) |
| `azcot_sd_climatology_{daily,monthly,seasonal}.nc` | as above | `sd_min`, `sd_mean`, `sd_max` (inches). **ERA5-Land 0.1° grid (3600 × 301)**, NaN over water, no `surface_type` |
| `azcot_{t2,wspd,sd}_histogram_monthly.nc` | 6 months | `{var}_hour_counts(time, bin, lat, lon)`: hours per 1-unit bin (1 °F, 1 kn, 1 in) and `n_hours` per month |
| `azcot_frostbite_{daily,monthly,seasonal}.nc` (Level 2) | as above | `frostbite_{red,amber,green,none}_share` (% of hours per TR-26-5 danger level), `frostbite_time_min` (shortest time to frostbite, min) |
| `azcot_frostbite_histogram_monthly.nc` (Level 2) | 6 months | `frostbite_hour_counts(time, bin, lat, lon)`: hours per frostbite-time bin (minutes) and `n_hours` |
| `azcot_snowfall_{daily,monthly,seasonal}.nc` (Level 2) | as above | `sf24_max`, `sf24_mean_annual_max`, `sf24_ge10_years`; `storm_max`, `storm_mean_annual_max`, `storm_ge20_years`; `sf72_max`, `sf72_mean_annual_max` (lb/ft², %); monthly/seasonal also `sf24_ge10_days`, `storm_ge20_per_year` |
| `azcot_snowfall_histogram_monthly.nc` (Level 2) | 6 months | `sf24_day_counts(time, sf24_bin, …)` (days per 0.5 lb/ft² bin of the day's largest 24-hour load), `storm_counts(time, storm_bin, …)` (storms per 1 lb/ft² bin), `n_days` |

Every file (except the SD files, which are on their own grid) also has `surface_type`, and every file has a `crs` grid-mapping variable. Thresholds and percentiles are coordinate dimensions (`wct_threshold`, `wct_consec_threshold`, `sl_threshold`, `percentile`) rather than one variable per threshold.

`intermediate/` holds `hourly_reduce/{wct,sl,t2,wspd,sd}/{mon}_{DD}.nc` (step 1: per-day min / mean / max, plus the mean of annual minima and maxima kept for validation) and `surface_type.nc` (step 2, with the diagnostic fields the rule uses). `histograms/` and `freeze_thaw/` (step 6) are also in `intermediate/`. `validation/validation_report.md` is written by step 5 and `validation/validation_report_extra.md` by step 8. `logs/` holds the SLURM logs.

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

### Air temperature, wind, snow depth (steps 6–8)

These three variables follow the same conventions as WCT and SL: true min, mean and max from all 720 hourly values per calendar day, and no Feb 29. On top of that, each has a **monthly histogram of hourly values** in 1-unit bins. Bin *u* holds hours with *u*−1 < value ≤ *u*, and the first and last bins are open-ended. The share of hours at or below any integer threshold *T* is `counts.sel(bin=slice(None, T)).sum("bin") / n_hours`. Sum over `time` for the whole season. This gives exact "% of hours colder than X" for *any* limit (e.g. an equipment rating of −53 °F), which the fixed 5 °F steps in `Metrics` can't. Percentiles follow from the cumulative sum at 1-unit resolution.

`t2_freeze_thaw_days` is the mean number of days per year (per month, or summed over the season) on which hourly 2T was both below and above 32 °F.

**`Metrics` is not used for these variables, because its stats for them are broken.** Checked against the raw hourly files at Fairbanks, Jan 15:

- **`Metrics` 2T is in kelvin**, but its `frequency_<T>` thresholds (0 … −75) are °F values. As a result every 2T frequency is 0%, while the raw data gives 22.5% of hours ≤ −20 °F. `min_2T` is again a mean of yearly lows.
- **The raw `*.WS10_knots.nc` files are in knots**, as named: `WS10` = sqrt(10U² + 10V²) × 1.943844 exactly, checked against the `*.10U.grib`/`*.10V.grib` files (m/s) and now by step 8 on every run. `Metrics` `averageWSPD` matches them, so the `Metrics` knot thresholds are fine, but `max_WSPD` equals `min_WS10` (6.99) while the true maximum is 13.34 kn. The pipeline uses the hourly values as they are, in knots.
  *Corrected 9 Oct 2026:* until then this README said the files were in m/s and step 6 multiplied them by 1.943844, so the earlier wind coverages were 1.94× too high. They have been rebuilt; the superseded intermediates are in `intermediate/_superseded_2026-10-09_wspd_x1.94/`.
- **`Metrics` snow depth is correct** (mean, max and the 8/15/20/40 in frequencies all match the raw data); it is used for validation.

**Missing snow-depth hours.** In the raw SD (ERA5-Land) files, **hours 01–23 of the last day of every month are entirely NaN in every year**; only 00 UTC survives. Three more 00 UTC hours are missing (2008-12-01, 2010-02-01, 2019-03-01). That is 690, 667, 668, 667, 484 and 1 missing hours for October through March.

Step 6 skips any all-NaN hour and records it: `n_missing_hours` in the daily intermediates, `missing_hours` in the histogram. Statistics use only the hours that exist, so the SD climatology for the last day of each month rests on 30 values instead of 720. Step 6 fails on any *partial* change of the data mask. (`Metrics` instead counts missing hours as "below threshold" while still dividing by 720, so its SD frequencies for those days are close to zero.) 2T and WSPD have no missing hours.

### Frostbite danger classes (steps 9, 11, 12)

TR-26-5 Tables 4–5 class frostbite danger by the time to frostbite of exposed, dry cheek skin: green ("slight", < 120 min), orange ("increased", < 45 min; called amber here) and red ("great", ≤ 5 min). That time depends on air temperature **and** wind together, so it can't be read from wind chill alone. The earlier maps approximated it with wind-chill cut-offs.

Step 9 reads the raw hourly 2T and WS10 for every hour and computes the time to frostbite with TR-26-5 **Eq. 5** (Nelson et al. 2002), exactly as published:

FT [min] = (−24.5 × (0.667 × WSPD[mph] × 8/5 + 4.8) + 2111) × (−4.8 − (2T[°F] − 32) × 5/9)^−1.668

- Eq. 5 is undefined at or above −4.8 °C (23.36 °F): no frostbite.
- Levels: **red** FT ≤ 5 min, **amber** 5 < FT ≤ 45, **green** 45 < FT ≤ 120, otherwise none.
- Above about 76 mph the wind term turns negative, beyond the range of the equation. Such hours are set to FT = 0 (red). With hourly-mean ERA5 wind this is very rare: 0–360 cell-hours a day, out of 125 million.
- Step 9 stores a frostbite-time histogram per calendar day, with bin edges at 5, 45 and 120 min, so the classes are exact. Step 11 aggregates the histograms to daily / monthly / seasonal shares and a monthly histogram.

Two caveats:
- **Eq. 5 does not reproduce TR-26-5's own Table 5.** At −10 °F and 5 mph it gives 14 min, against the table's 31. The two differ most at low wind and in the green band (see [plots.md](../plots/plots.md)). We use Eq. 5 because it's the report's stated method and applies to any temperature and wind.
- **Air temperature, not skin temperature.** AZCOT's WCT turns out to be computed from skin temperature (see above), so frostbite here is not consistent with the WCT coverages. It is consistent with TR-26-5.

### Snowfall loads (steps 10, 11, 12)

TR-26-5 §1 lists two design loads that depend on **snowfall**, not on the snow on the ground (SL):
- **tentage** must carry 10 lb/ft² from a 24-hour snowfall;
- **rigid shelters and portable hangars** must carry 20 lb/ft² from "storms lasting longer than one day", and are "cleared of snow between storms".

AZCOT has no snowfall, and differencing its SWE is unreliable (data-assimilation jumps; see [AZCOT_DATA_ISSUES.md](../AZCOT_DATA_ISSUES.md)). So step 10 reads **ERA5 hourly snowfall** (`sf`, m water equivalent per hour) from SNAP's existing ERA5 holdings, `/import/AKCASC/data/cds/reanalysis-era5-single-levels/sf`. It reads them in place; nothing is copied or modified. The load is snowfall × 204.724 lb/ft² per m w.e., the same factor as SL (TR-26-5 eq. 4).

- **One continuous series per winter.** Each task reads Sep 1 – Apr 30, so 24-hour windows and storms that cross a month, the new year or the season edge are complete. Only AZCOT months are kept (Jan–Mar and Oct–Dec of 1991–2020), so every calendar day pools 30 years like the other coverages. Snow that falls on Feb 29 counts, but there is no Feb 29 calendar day.
- **24-hour load:** the largest trailing 24-hour sum ending in each day. A **72-hour** load is computed the same way; it is a storm measure that doesn't depend on how a storm is defined.
- **Storm-total load.** A storm is a run of wet hours (≥ 0.1 mm w.e.) in which dry gaps last at most **12 h**. Its total is all snowfall from its first to its last wet hour, credited to the day it ends. A storm still going at the end of the season is credited to the last day with its full total.

  The definition is ours; the report gives none. **[storm_definition/README.md](storm_definition/README.md)** covers why it is needed, the evidence, how much it changes the results (it can flip a verdict in snowy maritime climates), its limitations and how to change it. We tested wet thresholds of 0.05 / 0.1 / 0.2 mm/h and gaps of 6 / 12 / 24 h at nine sites. Away from maritime climates the choice makes no difference. At Tromsø and Valdez, a 24-hour gap chains storms for 30–40 days, which is seasonal accumulation rather than a storm, while 6 h splits obvious multi-day events.
- **"Year"** means a calendar year's Jan–Mar plus Oct–Dec, the pooling all AZCOT coverages use.
- **Not masked.** Snowfall over glaciers and sea ice is real, unlike SL there. Use `surface_type` for symbology.

Record 24-hour loads at the example sites, in lb/ft²: Eureka 2.4, Oymyakon 2.7, Utqiagvik 3.4, Yellowknife 4.4, Fairbanks 4.6, Norilsk 5.7, Pituffik 6.6, Tromsø 7.3, Valdez 21.7. **Across most of the Arctic, tentage and rigid shelters are never threatened by a single snowfall or storm**; the exceptions are maritime mountains such as coastal Alaska, Norway and Iceland.

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

# submit the whole pipeline to SLURM (steps 1 and 6 in parallel, then steps 2-5 and 7-8)
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

| 6 | `sbatch step6_reduce_extra.slurm` | 3 variables × 182 × 720 raw hourly files → per-day min/mean/max, monthly histograms, freeze–thaw (one task per variable × month; SD is the slowest) | ~1–1.5 h |
| 7 | `$PY step7_extra_coverages.py` | 12 coverages for t2 / wspd / sd | ~2 min |
| 8 | `$PY step8_validate_extra.py` | checks, `validation/validation_report_extra.md` | ~5 min |
| 9 | `sbatch step9_reduce_frostbite.slurm` | raw 2T + WS10 (182 × 720 hours) → frostbite-time histograms per day (one task per day, 24 cores) | 7 min |
| 10 | `sbatch step10_reduce_snowfall.slurm` | SNAP ERA5 hourly snowfall, 31 winters → 24-h, 72-h and storm loads per day (one task per winter, 12 cores; I/O-bound) | 22 min |
| 11 | `$PY step11_level2_coverages.py [frostbite] [snowfall]` | 8 Level 2 coverages (peaks at ~17 GB RAM: use a compute node) | ~5 min |
| 12 | `$PY step12_validate_level2.py` | checks, `validation/validation_report_level2.md` (reads 5 cells × 8 months of snowfall point by point) | ~5 min |

`sbatch steps2to5.slurm` runs steps 2–5 together, `sbatch steps7to8.slurm` runs steps 7–8 (step 7 needs step 2's `surface_type`), and `sbatch steps11to12.slurm` runs steps 11–12 (needs steps 9 and 10). Steps 9 and 10 are resumable like step 1. Step 1 is **resumable**: each day is written atomically, and finished days are skipped on re-run, so just re-submit after an interruption. Steps 2–5 overwrite their outputs. Set `AZCOT_PRE_OUT=/some/dir` to write somewhere else (e.g. for a test run: `AZCOT_PRE_OUT=/tmp/test $PY step1_reduce_hourly.py --days jan_15`).

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

### Steps 6–8 (t2, wspd, sd)

Step 8 (`validation/validation_report_extra.md`) passes. Every check covers all 182 days and every cell:

| Check | Max difference |
|---|---:|
| `t2_mean` vs `Metrics` `averageTemp` (K → °F) | 1.1e-3 °F |
| our mean of yearly 2T minima vs `Metrics` `min_2T` (K → °F) | 2.1e-4 °F |
| `t2_min` ≤ `Metrics` `percentile_1` | 0 violations |
| `wspd_mean` vs `Metrics` `averageWSPD` (both knots) | 4.4e-5 kn |
| wind read by step 6 vs sqrt(10U² + 10V²) × 1.943844 from the GRIBs, 6 sample hours | 1.4e-4 kn |
| `sd_mean` / `sd_max` vs `Metrics` (m → in; complete days) | ≤ 1e-5 relative |
| Histogram totals = `n_hours` (all three variables) | 0 violations |
| SD share of hours ≥ 8/15/20/40 in vs `Metrics` (with `Metrics`' ÷720 undone) | 8.5e-6 %-points |

**The Atlas 2T "Lowest Recorded" rasters are not the true minimum.** Unlike the Atlas WCT rasters, which match exactly, the 2T rasters equal the raw-hourly minimum at only 27% of land cells and days, and are *warmer* at the other 73%. They are never colder, so the Atlas pipeline evidently missed hours. The worst case is 66 °N 67 °E on Nov 4: the raw data has a five-hour cold spell reaching −40.2 °F (1992-11-04 00 UTC, and the GRIB copy agrees), while the Atlas shows −6.3 °F. Step 8 therefore only checks that the Atlas is never colder than `t2_min`.

### Steps 9–12 (frostbite, snowfall loads)

Step 12 (`validation/validation_report_level2.md`) passes. The two independent recomputations use their own reading and arithmetic, not the step 9/10 functions:

| Check | Result |
|---|---:|
| Frostbite class counts vs. a direct recomputation from the raw 2T and WS10 files (5 cells × 3 days) | 0 hours different |
| Hours where Eq. 5 is defined lie between the hours with 2T ≤ 23 °F and ≤ 24 °F (t2 histogram), all cells and months | 0 violations |
| Frostbite histogram totals = `n_hours`; class shares sum to 100% | 0 violations; 1.5e-5 % |
| Daily-max 24-h and 72-h snowfall loads vs. pandas rolling sums, read point by point (5 cells, winter 2000–01) | 7.4e-6 lb/ft² |
| Daily-max storm totals vs. a plain-loop storm finder (same cells and winter) | 8.6e-6 lb/ft² |
| Record ≥ mean annual max ≥ 0; snowfall histogram day totals = `n_days` | 0 violations |

For reference, from the same report: on non-glacier land, the seasonal red share is 5.0% exact against 6.6% from the old wind-chill approximation. The average record 24-hour snowfall load is 4.6 lb/ft², with 2.8% of land ever reaching 10 lb/ft². The average record storm total is 8.3 lb/ft², with 4.4% of land ever reaching 20 lb/ft².

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
| `disk1/data/{mon}/{DD}/YYMMDDHH.{2T,WS10_knots}.nc` | frostbite time (step 9) |
| `disk1/data/{mon}/{DD}/YYMMDDHH.{10U,10V}.grib` | wind-unit check (step 8) |
| `/import/AKCASC/data/cds/reanalysis-era5-single-levels/sf/*_sf_{YYYY}_{MM}.nc` (SNAP ERA5, read-only, not AZCOT) | snowfall loads (step 10), Sep 1990 – Apr 2021 |
