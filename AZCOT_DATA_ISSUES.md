# AZCOT dataset: issues found during independent reprocessing

**Dataset:** `/beegfs/SNAP/rltorgerson/AZCOT` (`disk1/data`, `disk1/Metrics`, `disk2/Atlas`), described in ERDC/CRREL TR-26-5 and SR-25-2.
**Prepared by:** SNAP, University of Alaska Fairbanks (J. Paul), October 2026.

We recomputed the cold-season (Oct–Mar, 1991–2020) statistics directly from the hourly files in `disk1/data` and compared them with `disk1/Metrics` and the `disk2/Atlas` rasters. Most of the dataset reproduces exactly. For example, `Metrics` means and percentiles match the hourly data to within float32 round-off, and the land-wide numbers in TR-26-5 reproduce to the first decimal. The items below are the exceptions.

Each issue gives the evidence, so it can be checked. Grid cells are given as lat/lon on the 0.25° ERA5 grid; temperatures are in °F unless noted.

## Summary

| # | Where | Issue | Severity |
|---|---|---|---|
| 1 | `Metrics` `min_WCT`, `min_2T` | "Minimum" is the 30-year **mean of annual minima**, not the record low | High |
| 2 | `Metrics` Feb 29 files | `min_WCT` divides the sum of **8** yearly minima by **30** | High (one day) |
| 3 | `Metrics` `daily_2T_stats`, `6h_2T_stats` | Values are in **kelvin**, but thresholds are in °F, so every 2T frequency is 0% | High |
| 4 | `disk1/data/*.WS10_knots.nc`, `Metrics` WSPD | Wind is in **m/s**, not knots; frequency thresholds were applied to m/s; `max_WSPD` duplicates `min_WS10` | High |
| 5 | `disk1/data/*.SD.nc` | **Hours 01–23 of the last day of every month are missing** (all NaN) in every year | Medium |
| 6 | `Metrics` `daily_SD_stats` | Missing hours count as "not exceeding" and the divisor stays 720, so frequencies are biased low | Medium |
| 7 | `disk2/Atlas` 2T Extreme rasters | "Lowest recorded" 2T is warmer than the true hourly minimum at 73% of cells and days | High |
| 8 | `Metrics` (all) | No `units` attributes; the SD mean variable is named `averageSL` | Low |
| 9 | TR-26-5 Tables 4, 5, 12, 18 | Internal inconsistencies in the operational tables | Low–Medium |

---

## 1. `min_WCT` and `min_2T` are means of annual minima, not record lows

TR-26-5 §2.3.1 and SR-25-2 §2 describe the Minimum metric as the lowest value in 30 years, and `disk2/Atlas/zScripts/metricCalculation_frequency.py` computes it that way (`df_min.min(axis=1)`). The `Metrics` WCT and 2T files instead hold the **mean over the 30 years of each year's lowest hourly value** for that day.

**Evidence: Jan 15, using the 720 hourly files in `disk1/data/jan/15`**

| Cell | Stored `min_WCT` | Mean of 30 annual minima | True minimum |
|---|---:|---:|---:|
| Fairbanks, 64.75 N 147.75 W | −18.70 | −18.70 | −62.66 |
| Utqiagvik, 71.25 N 156.75 W (Jan 15) | −41.17 | −41.17 | −75.52 |

The match is exact at every cell and day tested. Because of this, `min_WCT` is warmer than `percentile_1` at **every** grid cell. `min_2T` behaves the same way: at Fairbanks on Jan 15 it is 251.90 K (−6.25 °F), equal to the mean of the yearly minima.

**Impact.** Any product built on `min_*` understates cold extremes by tens of degrees. The Atlas WCT "Minimum" rasters are **not** affected: they match the true minimum exactly. **`max_SL` is the true maximum**, so the two extreme fields use different conventions.

**Suggested fix:** recompute `min_*` as the minimum over all 720 hours, or rename the field (e.g. `mean_annual_min`) and document it.

## 2. Feb 29: `min_WCT` divided by 30 instead of 8

Feb 29 files pool only the 8 leap years (1992 … 2020, 192 hours), which is expected. But `min_WCT` on Feb 29 equals **sum(8 yearly minima) / 30**.

**Evidence: Feb 29**

| Cell | Stored `min_WCT` | Sum ÷ 30 | Mean of 8 yearly minima |
|---|---:|---:|---:|
| Utqiagvik | −11.14 | −11.14 | −41.77 |
| Fairbanks | −2.76 | −2.76 | −10.36 |

The other Feb 29 fields (`averageTemp`, `percentile_*`, `frequency_*`) match the 192 hours exactly. The bug shows up as a spike at Mar 1 in any daily time series.

**Suggested fix:** divide by the number of years present, or document that Feb 29 statistics come from 8 years.

## 3. `Metrics` 2T is in kelvin, but its thresholds are in °F

`daily_2T_stats` stores temperatures in **kelvin**. At Fairbanks on Jan 15, `averageTemp` is 255.14 K, which equals the hourly mean of −0.42 °F exactly, and `percentile_1` is 230.22 K. The `frequency_<T>` thresholds (0 … −75) are °F values, but they were applied to the kelvin data, so **no hour ever qualifies**.

| Fairbanks, Jan 15 | `Metrics` | Hourly data |
|---|---:|---:|
| `frequency_-20` | 0.0% | 22.5% of hours ≤ −20 °F |
| `frequency_-40` | 0.0% | 4.9% of hours ≤ −40 °F |

`consecutive_<T>` uses the same thresholds and is very likely affected the same way (not checked separately). We have not checked whether the Atlas 2T frequency maps were built from these files.

**Suggested fix:** convert 2T to °F before thresholding, as was done for WCT, and add `units` attributes.

## 4. Wind files are in m/s, not knots; `max_WSPD` is wrong

The hourly `disk1/data/*/*.WS10_knots.nc` files contain `WS10 = sqrt(10U² + 10V²)`, per their own `history` attribute, which is in **m/s**. `Metrics` `averageWSPD` matches the hourly m/s mean exactly (Fairbanks, Jan 15: 5.0882). So the WSPD frequency thresholds (8, 13, 15 … 50, documented as knots in SR-25-2) were applied to **m/s**:

| Fairbanks, Jan 15 | Value |
|---|---:|
| `frequency_8` (stored) | 17.5% |
| Share of hours ≥ 8 m/s | 17.5% |
| Share of hours ≥ 8 **kn** | 54.2% |

Also at Fairbanks on Jan 15, `max_WSPD` = `min_WS10` = 6.9944, while the true maximum of the 720 hours is 13.34 m/s. This looks like one field was copied into the other.

**Suggested fix:** rename the hourly files, or convert them to knots, before computing the stats; recompute `max_WSPD` and `min_WS10`.

## 5. Missing snow-depth hours: last day of every month

In `disk1/data/*/*/YYMMDDHH.SD.nc` (ERA5-Land `sde`), **hours 01–23 of the last day of each month are entirely NaN in every year**; only 00 UTC is present. Three more 00 UTC hours are also all-NaN: 2008-12-01, 2010-02-01 and 2019-03-01.

| Month | Oct | Nov | Dec | Jan | Feb | Mar |
|---|---:|---:|---:|---:|---:|---:|
| Missing hours (of 30 × days × 24) | 690 | 667 | 668 | 667 | 484 | 1 |

So the statistics for the last day of each month rest on 30 hourly values instead of 720. This looks like an artifact of downloading ERA5-Land month by month (time-step bookkeeping at month ends). SWE (`*.SWE.grib`), 2T, WCT and wind have **no** missing hours.

**Suggested fix:** re-download the missing hours from the Copernicus CDS (ERA5-Land hourly snow depth).

## 6. `Metrics` SD frequencies are biased by the missing hours

`daily_SD_stats` `frequency_8/15/20/40` count the missing hours as "below threshold" and still divide by 720. On the last day of each month this pushes the frequencies to nearly zero, and it lowers monthly averages by about 3 percentage points. Rebuilding the hour counts (frequency × 7.2) and dividing by the hours actually present reproduces our values to within 1e-5 percentage points. `averageSL` (SD mean) and `max_SD` are correct.

**Suggested fix:** divide by the number of non-missing hours (or fill the gaps; see issue 5).

## 7. Atlas 2T "Lowest Recorded" rasters are not the true minimum

`disk2/Atlas/{mon}/Daily/{DD}/2T/Extreme/*_2T_min.tif` disagrees with the hourly data. We compared it every 7th day, about 1.6 million land cell-days:

| Comparison | Share of cell-days |
|---|---:|
| Equals the hourly minimum | 27% |
| **Warmer** than the hourly minimum | 73% |
| Colder than the hourly minimum | 0% |

So the raster is never colder than the true minimum, which suggests hours were missed when it was built. The worst case is 66.0 N 67.0 E on Nov 4. The hourly data has a five-hour cold spell reaching **−40.2 °F** (1992-11-03 22 UTC to 11-04 02 UTC; the GRIB copy agrees), but the Atlas shows −6.3 °F. On the six worst days, the mean difference across land cells is 1.5–2.3 °F and the largest single-cell difference is 28–34 °F.

The Atlas **WCT** Extreme rasters, by contrast, match the true hourly minimum exactly, and the seasonal one reproduces TR-26-5's −86.7 °F land average.

**Suggested fix:** rebuild the 2T Extreme layers from all 720 hours per day (the WCT workflow appears correct).

## 8. Metadata

- **No `units` attributes** in any `Metrics` file. Units have to be inferred, and they are inconsistent: 2T in K, WCT in °F, WSPD in m/s, SD in m, SL in lb/ft².
- **Misnamed variable:** `daily_SD_stats` stores the snow-depth mean as `averageSL`.
- **No CRS:** none of the NetCDF files declare a CRS or `grid_mapping` (the data are implicitly EPSG:4326).
- **Differing latitude order:** the hourly files store latitude 90 → 60, while `Metrics` stores 60 → 90. This is not an error, but it is easy to trip on.
- **Unlabeled `var29`:** the `*.var29.{grib,nc}` files are ERA5 *instantaneous 10 m wind gust* (`I10FG`, parameter 228029, m/s), present only at 06 and 18 UTC. Labeling them would make the dataset's only gust data findable.

## 9. TR-26-5 operational tables

- **Table 4 (wind chill / frostbite):** the 15 °F column duplicates the 10 °F column (e.g. 6, 6 at 15 mph; NWS gives 0 °F).
- **Table 4 green shading:** green ("frostbite < 120 min") extends to wind chills of +19 °F, where Eq. 5 gives no frostbite within 120 min (frostbite in < 120 min begins near WCT 0 °F). Table 5 also shades ">120" cells green.
- **Table 5 vs. Eq. 5:** Eq. 5 doesn't reproduce Table 5's minutes; at −10 °F and 5 mph it gives 14 min, against the table's 31.
- **Table 12:** "Rechargeable dry cell Type III and IV" is listed as Zone 1 with a −22 °F limit, which falls in Zone 3.
- **Table 18:** GO-75 appears twice, with limits of 50 °F and −50 °F.

## Observations (expected behavior, worth documenting)

- **Glacier cap in snow load.** SL ≈ 2047.24 lb/ft² over ice sheets and ice caps is ERA5's constant 10 m water equivalent on glacier points (Muñoz-Sabater et al. 2021, ESSD, §2.1), not a real load. That is about 10,000 cells. A further ~4,200 partly glaciated cells accumulate snow every year without limit (500–2,000 lb/ft²). Flagging both in the data, not only masking them in figures, would help users.
- **Snow load is accumulated snow on the ground, not snowfall.** SL is computed correctly from ERA5 SWE: SL = SWE[in] × 5.2, where 5.2 lb/ft² per inch is the weight of water, so no snow-density assumption is involved. We matched it exactly against `*.SWE.grib`. Two points are worth stating in the documentation:
  - **The SWE files are named after ERA5's own parameter, "snow depth" (`sd`, 141), but hold metres of water equivalent.** The separate `SD` files are physical depth from ERA5-Land. The names invite confusion between the two.
  - **ERA5 SWE is an instantaneous state variable**, so SL describes the snowpack at each hour. It fits the seasonal-accumulation design loads (life-sustaining structures 25 lb/ft², semipermanent 48 lb/ft²), but not the tentage (one 24-hour snowfall, 10 lb/ft²) or rigid-shelter (one multi-day storm, 20 lb/ft²) criteria that TR-26-5 §1 lists alongside them.

  Differencing hourly SWE is not a reliable substitute. It includes data-assimilation increments: in January, when there is essentially no melt, hourly SWE losses over land are 3–5× larger at 00, 03, 10 and 22 UTC than at other hours, and every hourly change above 1 lb/ft² falls on those hours. It also nets out melt and sublimation. ERA5 hourly snowfall (`sf`, parameter 144, accumulated over the hour ending at the valid time) gives 24-hour and storm-total snowfall loads directly, and would be the better input for those criteria.
- **Report averages.** The land-wide statistics in TR-26-5 are unweighted grid-cell means, which over-weight high latitudes on a lat/lon grid. For example, the share of hours with WCT ≤ −65 °F is 7.66% by pixel mean but 5.87% area-weighted.

---

*All numbers above can be reproduced with the scripts in this repository: `eda/`, `preprocess/` (step 5 and step 8 validation reports) and `eda/scripts/check_atlas_min.py`. Contact SNAP for the code or the recomputed coverages.*
