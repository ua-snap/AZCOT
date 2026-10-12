# AZCOT dataset: issues found during independent reprocessing

**Dataset:** `/beegfs/SNAP/rltorgerson/AZCOT` (`disk1/data`, `disk1/Metrics`, `disk2/Atlas`), described in ERDC/CRREL TR-26-5 and SR-25-2.
**Prepared by:** SNAP, University of Alaska Fairbanks (J. Paul), October 2026.

We recomputed the cold-season (Oct–Mar, 1991–2020) statistics directly from the hourly files in `disk1/data` and compared them with `disk1/Metrics` and the `disk2/Atlas` rasters. Most of the dataset reproduces exactly. For example, `Metrics` means and percentiles match the hourly data to within float32 round-off, and the land-wide numbers in TR-26-5 reproduce to the first decimal. One exception to the percentile match: the WCT percentiles and frequencies for Oct 4–6 appear to have been computed from a different set of hours than the delivered files. On Oct 4 and 5, every frequency is a multiple of 1/744 (31 × 24 hours) rather than 1/720. The items below are the exceptions.

> **Correction, 9 October 2026.** An earlier version of this document (issue 4) said the hourly wind files are in m/s, not knots. That was our error: they are in knots, as their names say, and the `Metrics` wind thresholds are therefore correct. The same check found a new issue (10): wind chill is computed from **skin** temperature, not 2 m air temperature.

> **Revision, 12 October 2026.** Before sending this document we re-verified every High and Medium issue with new code. It reads only the original files and covers every grid cell, all 183 days and every hourly file (131,232 hours per variable). It is cross-checked against the GRIB source files and an independent copy of ERA5/ERA5-Land. All eight issues hold, but several statements were corrected or narrowed:
> - issue 3 does not affect the 6-hour files or the `consecutive_*` fields;
> - issue 4 is a mean of annual maxima, not a copied field;
> - issue 5's February count was wrong;
> - issue 10 applies to 95% of hours, not all of them.
>
> We also identified the likely mechanisms for issues 1, 2, 4, 5 and 7.

Each issue gives the evidence, so it can be checked. Grid cells are given as lat/lon on the 0.25° ERA5 grid; temperatures are in °F unless noted.

## Summary

| # | Where | Issue | Severity |
|---|---|---|---|
| 1 | `Metrics` `daily_*_stats`: `min_WCT`, `min_2T`, `min_SKT` | "Minimum" is the 30-year **mean of annual minima**, not the record low (the 6-hour files are correct) | High |
| 2 | `Metrics` Feb 29 files | `min_*` and all `consecutive_*` fields divide the sum of **8** yearly values by **30** | High (one day) |
| 3 | `Metrics` `daily_2T_stats` | Values are in **kelvin**, but the `frequency_*` thresholds are in °F, so every daily 2T frequency is 0% | Medium |
| 4 | `Metrics` WSPD | `max_WSPD` (and its duplicate `min_WS10`) is the **mean of annual maxima**, not the highest value | Medium |
| 5 | `disk1/data/*.SD.nc` | **Hours 01–23 of the last day of every month are missing** (all NaN) in every year | Medium |
| 6 | `Metrics` `daily_SD_stats` | Missing hours count as "not exceeding" and the divisor stays 720, so frequencies are biased low | Medium |
| 7 | `disk2/Atlas` daily 2T Extreme rasters | "Lowest recorded" 2T is built from only **4 of 24 UTC hours** on most days, so it is warmer than the true minimum at 72% of cell-days | High |
| 8 | `Metrics` (all) | No `units` attributes; the SD mean variable is named `averageSL`; some 6-hour files lack a minimum variable | Low |
| 9 | TR-26-5 Tables 4, 5, 12, 18 | Internal inconsistencies in the operational tables | Low–Medium |
| 10 | `disk1/data/*.WCT.nc` (and everything built on it) | For 95% of hours, wind chill uses **skin temperature (SKT)**, not 2 m air temperature as TR-26-5 eq. 3 states. Over land the stored WCT is ~3–4 °F colder and roughly doubles the hours ≤ −65 °F. | High |

---

## 1. Daily `min_WCT`, `min_2T` and `min_SKT` are means of annual minima, not record lows

TR-26-5 §2.3.1, SR-25-2 §3.2 and `disk1/README.docx` describe the Minimum metric as the lowest value in 30 years, and `disk2/Atlas/zScripts/metricCalculation_frequency.py` computes it that way (`df_min.min(axis=1)`). The `Metrics` `daily_WCT_stats`, `daily_2T_stats` and `daily_SKT_stats` files instead hold the **mean over the 30 years of each year's lowest hourly value** for that day.

**Evidence: Jan 15, using the 720 hourly files in `disk1/data/jan/15`**

| Cell | Stored `min_WCT` | Mean of 30 annual minima | True minimum |
|---|---:|---:|---:|
| Fairbanks, 64.75 N 147.75 W | −18.70 | −18.70 | −62.66 |
| Utqiagvik, 71.25 N 156.75 W | −41.17 | −41.17 | −75.52 |

The match is exact (within 1.2e-4) in **every grid cell on all 182 non-leap days**, for `min_WCT`, `min_2T` and `min_SKT`. None of the three ever equals the true minimum. As a result, `min_WCT` is warmer than `percentile_1` in every cell on every one of those days, by 17–25 °F on average (daily grid means) and by up to 74 °F in a single cell. `min_2T` at Fairbanks on Jan 15 is 251.90 K (−6.25 °F), equal to the mean of the yearly minima.

**The 6-hour files are correct.** Every 6-hour minimum (`6h_WCT_stats`, `6h_2T_stats`, `6h_SKT_stats`) is the true minimum of its 180 hours, with zero difference (where the variable exists; see issue 8). The Atlas WCT "Minimum" rasters also match the true minimum exactly. The problem is confined to the daily `Metrics` files.

**Likely mechanism.** The published `zScripts/metricCalculation_consecutive.py` computes the extreme **per year**, adds up the yearly results and divides by a hard-coded `num_years = 30`. That reproduces these values exactly. The daily files contain that script's fields (`consecutive_*` plus the extreme). The 6-hour files contain only the fields of `metricCalculation_frequency.py`, which takes the true minimum.

![Fairbanks daily minima](verification/figures/issue1_2_fairbanks_min_wct.png)

*Fairbanks, every day of the season. The stored `min_WCT` (orange) lies exactly on the mean of the 30 annual minima. The true minimum and the Atlas raster (blue) are 20–50 °F colder. The spike on Feb 29 is issue 2.*

**Impact.** Any product built on the daily `min_*` fields understates cold extremes by tens of degrees. **`max_SL` is the true maximum**, so the daily extreme fields do not all follow one convention.

**Suggested fix:** recompute `min_*` as the minimum over all 720 hours (as the 6-hour files already do), or rename the field (e.g. `mean_annual_min`) and document it.

## 2. Feb 29: yearly values divided by 30 instead of 8

Feb 29 files pool only the 8 leap years (1992 … 2020, 192 hours), which is expected. But on Feb 29, `min_WCT`, `min_2T` and `min_SKT` equal **sum(8 yearly minima) / 30**. All of the WCT `consecutive_*` fields are likewise **sum(8 yearly values) / 30**: dividing by 8 instead would change them by up to 17.6 hours. Both follow from the hard-coded 30 in the consecutive script (issue 1).

**Evidence: Feb 29**

| Cell | Stored `min_WCT` | Sum ÷ 30 | Mean of 8 yearly minima |
|---|---:|---:|---:|
| Utqiagvik | −11.14 | −11.14 | −41.77 |
| Fairbanks | −2.76 | −2.76 | −10.36 |

The match is exact in every grid cell. The other Feb 29 fields (`averageTemp`, `percentile_*`, `frequency_*`) match the 192 hours exactly. The one exception is wind: on Feb 29, `max_WSPD` is divided by 8, while its duplicate `min_WS10` is divided by 30. The bug shows up as a spike **on Feb 29** in any daily time series (see the figure in issue 1).

**Suggested fix:** divide by the number of years present, or document that Feb 29 statistics come from 8 years.

## 3. `daily_2T_stats` is in kelvin, but its frequency thresholds are in °F

`daily_2T_stats` stores temperatures in **kelvin**. At Fairbanks on Jan 15, `averageTemp` is 255.14 K, which equals the hourly mean of −0.42 °F exactly, and `percentile_1` is 230.22 K. The `frequency_<T>` thresholds (0 … −75) are °F values, but they were applied to the kelvin data, so **no hour ever qualifies**. All 16 daily 2T frequency fields are exactly 0 in every grid cell on every day.

| Fairbanks, Jan 15 | `Metrics` | Hourly data |
|---|---:|---:|
| `frequency_-20` | 0.0% | 22.5% of hours ≤ −20 °F |
| `frequency_-40` | 0.0% | 4.9% of hours ≤ −40 °F |

The rest of the 2T thresholding is correct. The daily `consecutive_*` fields and the `6h_2T_stats` frequencies hold correct °F values: at least 99.8% of cells match the hourly data on every day, and the rest are ties at a threshold. **The Atlas 2T frequency maps are also correct** (at least 99.9% of cells match), so the published maps are not affected. Only the daily `frequency_*` fields are.

![2T frequency](verification/figures/issue3_2t_frequency.png)

*Land-mean share of hours ≤ −40 °F, by day. The `daily_2T_stats` field is 0 all season, while the hourly data and the Atlas raster agree.*

**Suggested fix:** convert 2T to °F before thresholding in the daily frequency step, as was done for the 6-hour files, and add `units` attributes.

## 4. `max_WSPD` is the mean of annual maxima (wind units are correct)

*Corrected 9 October 2026: an earlier version said the wind files were in m/s. They are in knots.*

The hourly `disk1/data/*/*.WS10_knots.nc` files are in **knots**, as named. We sampled one random hour on each of the 183 days. In every one, `WS10` equals sqrt(10U² + 10V²) × 1.943844 (the m/s-to-knots factor) in every grid cell, using the `*.10U.grib`/`*.10V.grib` files (units "m s**-1"). For example, 1994-01-15 23 UTC at 62.0 N 47.75 W: 10U = −33.51, 10V = 10.08 m/s → 34.99 m/s = 68.02 kn, and `WS10` = 68.02. ERA5 u10/v10 from an independent copy of ERA5 agree.

We were misled by the files' `history` attribute, which records only the intermediate step (`cdo ... -sqrt -add -sqr 10U -sqr 10V`, i.e. m/s); the conversion to knots that followed is not recorded. Since `Metrics` `averageWSPD` and the `frequency_*` fields match the hourly values exactly, the `Metrics` WSPD statistics are in knots and their knot thresholds (8, 13 … 50) are applied correctly.

One problem remains. On every non-leap day, `max_WSPD` and `min_WS10` are bit-for-bit identical. **Both hold the mean of the 30 annual maxima** in every grid cell (within 1.1e-5), never the true maximum. At Fairbanks on Jan 15 that is 6.99 kn, while the true maximum of the 720 hours is 13.34 kn. This is the same per-year-then-average convention as issue 1, and it is what `metricCalculation_consecutive.py` computes for `max_WSPD`. `min_WS10` is a misnamed copy. The 6-hour `max_wspd` is the true maximum.

![Fairbanks wind](verification/figures/issue4_fairbanks_max_wspd.png)

*Fairbanks: `max_WSPD` (orange) lies exactly on the mean of the annual maxima. The true maximum (blue) is roughly twice as large.*

**Suggested fix:** recompute `max_WSPD` as the maximum over all 720 hours and drop or rename `min_WS10`; add a history entry (or `units` attribute) for the knot conversion.

## 5. Missing snow-depth hours: last day of every month

In `disk1/data/*/*/YYMMDDHH.SD.nc` (ERA5-Land `sde`), **hours 01–23 of the last day of each month are entirely NaN in every year**; only 00 UTC is present. Three more 00 UTC hours are also all-NaN: 2008-12-01, 2010-02-01 and 2019-03-01. Every file exists, its stored valid time matches its name, and every other file has the same 383,866 land cells.

| Month | Oct | Nov | Dec | Jan | Feb | Mar |
|---|---:|---:|---:|---:|---:|---:|
| All-NaN hourly files | 690 | 667 | 668 | 667 | 668 | 1 |

(February counts 483 files on Feb 28 in the 21 non-leap years, 184 on Feb 29, and the 2010-02-01 hour.)

So the statistics for the last day of each month rest on 30 hourly values instead of 720.

**Likely mechanism.** Every missing field belongs to the **00 UTC ERA5-Land forecast cycle that starts on the last day of the month**: the files' own forecast reference time is that day, at steps 1–23. In the three months where the last day is complete (Nov 2008, Jan 2010, Feb 2019), the missing hour is that cycle's step 24 (00 UTC on the 1st) instead. The cycle that straddles two monthly downloads loses its hours on one side or the other.

The data exist upstream. On all 146 month-end dates where the AZCOT 12 UTC file is empty, an independent ERA5-Land copy (daily 12 UTC snow depth) has a complete field. On 642 normal dates it matches AZCOT to within its packing precision (0.00025 m).

SWE (`*.SWE.grib`), 2T, SKT, WCT and wind have **no** missing or NaN values in any hour.

![SD missing hours](verification/figures/issue5_sd_missing_hours.png)

*Number of years (of 30) with an all-NaN snow-depth file, by day and UTC hour.*

**Suggested fix:** re-download (or re-convert) the missing hours from the Copernicus CDS (ERA5-Land hourly snow depth).

## 6. `Metrics` SD frequencies are biased by the missing hours

`daily_SD_stats` `frequency_8/15/20/40` count the missing hours as "below threshold" and still divide by 720 (exact in every cell on every day). On the last day of each month this pushes the frequencies to nearly zero. It also lowers the monthly averages (land mean of daily `frequency_8`): by 1.8 percentage points in October, 2.7–2.9 points in November–January, 5.6 points in February (Feb 28 and Feb 29 are both affected) and not at all in March. Rebuilding the hour counts (frequency × 7.2) and dividing by the hours actually present reproduces our values to within 1e-5 percentage points. `averageSL` (the SD mean) and `max_SD` are correct (in metres).

![SD monthly bias](verification/figures/issue6_sd_monthly_bias.png)

**Suggested fix:** divide by the number of non-missing hours (or fill the gaps; see issue 5).

## 7. Atlas daily 2T "Lowest Recorded" rasters are not the true minimum

`disk2/Atlas/{mon}/Daily/{DD}/2T/Extreme/*_2T_min.tif` disagrees with the hourly data. We compared every day of the season over the 61,532 land cells, 11.3 million cell-days in all:

| Comparison | Share of cell-days |
|---|---:|
| Equals the hourly minimum | 28% |
| **Warmer** than the hourly minimum | 72% |
| Colder than the hourly minimum | 0% |

**Mechanism.** In every cell on every day, the raster equals the **exact minimum over a fixed subset of UTC hours** (all 30 years):
- **Oct–Dec and Feb–Mar (152 days): only 11, 15, 19 and 23 UTC.** The other 20 hours are never used.
- **January (31 days): 08–23 UTC.** Hours 00–07 are never used.

The worst case is 66.0 N 67.0 E on Nov 4. The hourly data has a five-hour cold spell reaching **−40.2 °F** (1992-11-03 22 UTC to 11-04 02 UTC; the GRIB copy agrees), but the Atlas shows −6.3 °F, which is the minimum of 11, 15, 19 and 23 UTC. On the six worst days, the mean difference across land cells is 1.5–2.3 °F and the largest single-cell difference is 29–34 °F.

![Atlas 2T hours](verification/figures/issue7_atlas_2t_hours.png)

*Top: UTC hours that contain a value colder than the Atlas raster somewhere, so they cannot have been in its pool. Bottom: share of land cells where the Atlas value is warmer than the true minimum.*

The rest of the Atlas extremes workflow is correct. The **6-hour** 2T Extreme rasters equal the true 6-hour minima exactly. The Atlas **WCT** Extreme rasters match the true hourly minimum exactly, and the seasonal one reproduces TR-26-5's −86.7 °F land average.

**Suggested fix:** rebuild the daily 2T Extreme layers from all 24 hours of each day (the 6-hour 2T layers and the WCT workflow already do this).

## 8. Metadata

- **No `units` attributes** in any `Metrics` file. Units have to be inferred, and they are inconsistent: 2T in K, WCT in °F, WSPD in knots, SD in m, SL in lb/ft².
- **Misnamed variables:** `daily_SD_stats` stores the snow-depth mean as `averageSL`. The 6-hour WCT minimum is named `min_stl1` in 604 files and `min_wct` in 124. The four Jan 2 files (`jan_02_6h_*_WCT_stats.nc`) have **no minimum variable at all**.
- **No CRS:** none of the NetCDF files declare a CRS or `grid_mapping` (the data are implicitly EPSG:4326).
- **Differing latitude order:** the hourly files store latitude 90 → 60, while `Metrics` stores 60 → 90. This is not an error, but it is easy to trip on.
- **Unlabeled `var29`:** the `*.var29.{grib,nc}` files are ERA5 *instantaneous 10 m wind gust* (`I10FG`, parameter 228029, m/s), present only at 06 and 18 UTC. Labeling them would make the dataset's only gust data findable.

## 9. TR-26-5 operational tables

- **Table 4 (wind chill / frostbite):** the 15 °F column duplicates the 10 °F column (e.g. 6, 6 at 15 mph; NWS gives 0 °F).
- **Table 4 green shading:** green ("frostbite < 120 min") extends to wind chills of +19 °F, where Eq. 5 gives no frostbite within 120 min (frostbite in < 120 min begins near WCT 0 °F). Table 5 also shades ">120" cells green.
- **Table 5 vs. Eq. 5:** Eq. 5 doesn't reproduce Table 5's minutes; at −10 °F and 5 mph it gives 14 min, against the table's 31.
- **Table 12:** "Rechargeable dry cell Type III and IV" is listed as Zone 1 with a −22 °F limit, which falls in Zone 3.
- **Table 18:** GO-75 appears twice, with limits of 50 °F and −50 °F.

## 10. Wind chill is computed from skin temperature, not 2 m air temperature

TR-26-5 eq. 3, SR-25-2 eq. 3 and the Atlas map captions define WCT from 2 m air temperature (2T) and 10 m wind speed (NWS 2001 formula, °F and mph). Each hourly `disk1/data/*/*.WCT.nc` file matches exactly one version of that formula (wind converted from knots to true mph) to within 0.01 °F in every grid cell:

| Temperature used | Hours | Share | When |
|---|---:|---:|---|
| **Skin temperature (SKT)** | 124,653 | 95% | all other days |
| 2 m air temperature (2T), as documented | 6,579 | 5% | all hours of **Dec 1–9** in every year; Nov 2 in 2000–2003 (all hours) and 3 hours in 2004 |

No hour matches neither. The `2T.nc` and `SKT.nc` files match their GRIB sources (`2t`, `skt`), and `2T.nc` matches an independent copy of ERA5 t2m, so the labels are not swapped.

![WCT source by day](verification/figures/issue10_wct_source_by_day.png)

*Which temperature each day's hourly `WCT.nc` files were built from, as a share of the day's 720 hours.*

Over snow in the Arctic winter, the skin is usually colder than the air at 2 m (a surface inversion), so the stored WCT is mostly too cold. The table uses non-glacier land: the Atlas land mask minus ERA5 glacier-cap cells, 51,567 cells, unweighted means.

| | Jan 15: stored WCT | Jan 15: WCT from 2T (eq. 3) | Oct–Mar: stored WCT | Oct–Mar: WCT from 2T (eq. 3) |
|---|---:|---:|---:|---:|
| Mean WCT difference (2T-based − stored) | | +4.2 °F | | +3.1 °F |
| Record low, land mean difference | | +4.7 °F (95th pct +18, max +38) | | +5.1 °F (95th pct +17, max +35) |
| Share of hours ≤ −40 °F | 46.9% | 39.7% | 26.6% | 21.5% |
| **Share of hours ≤ −65 °F** | **11.1%** | **5.4%** | **4.4%** | **2.0%** |

| Site (Jan 15) | Stored WCT | WCT from 2T |
|---|---:|---:|
| Eureka, NU (80.0 N 86.0 W): hours ≤ −40 °F | 86.7% | 58.5% |
| Utqiagvik, AK: record low | −75.5 °F | −69.9 °F |
| Oymyakon, RU: record low | −84.2 °F | −87.7 °F |

The effect is largest in the high Arctic (north of about 75 °N), in calm areas and on elevated terrain, and smallest in the southern boreal forest. It can go either way locally: on 17% of non-glacier land cells, the 2T-based record low is colder.

Every WCT product inherits it: the `Metrics` WCT statistics, the Atlas WCT maps, and TR-26-5's headline numbers. For example, the Atlas seasonal raster gives 7.66% of hours ≤ −65 °F (the Army materiel requirement) as a land average. With WCT from 2T, the same calculation gives 3.9%. The seasonal record-low land average would be −81.3 °F instead of −86.7 °F.

**Suggested fix:** recompute WCT from 2T for all hours, or document that WCT is a skin-temperature wind chill and say why.

## Observations (expected behavior, worth documenting)

- **Glacier cap in snow load.** SL ≈ 2047.24 lb/ft² over ice sheets and ice caps is ERA5's constant 10 m water equivalent on glacier points (Muñoz-Sabater et al. 2021, ESSD, §2.1), not a real load. That is about 10,000 cells. A further ~4,200 partly glaciated cells accumulate snow every year without limit (500–2,000 lb/ft²). Flagging both in the data, not only masking them in figures, would help users.
- **Snow load is accumulated snow on the ground, not snowfall.** SL is computed correctly from ERA5 SWE: SL = SWE[in] × 5.2, where 5.2 lb/ft² per inch is the weight of water, so no snow-density assumption is involved. We matched it exactly against `*.SWE.grib`. Two points are worth stating in the documentation:
  - **The SWE files are named after ERA5's own parameter, "snow depth" (`sd`, 141), but hold metres of water equivalent.** The separate `SD` files are physical depth from ERA5-Land. The names invite confusion between the two.
  - **ERA5 SWE is an instantaneous state variable**, so SL describes the snowpack at each hour. It fits the seasonal-accumulation design loads (life-sustaining structures 25 lb/ft², semipermanent 48 lb/ft²), but not the tentage (one 24-hour snowfall, 10 lb/ft²) or rigid-shelter (one multi-day storm, 20 lb/ft²) criteria that TR-26-5 §1 lists alongside them.

  Differencing hourly SWE is not a reliable substitute. It includes data-assimilation increments: in January, when there is essentially no melt, hourly SWE losses over land are 3–5× larger at 00, 03, 10 and 22 UTC than at other hours, and every hourly change above 1 lb/ft² falls on those hours. It also nets out melt and sublimation. ERA5 hourly snowfall (`sf`, parameter 144, accumulated over the hour ending at the valid time) gives 24-hour and storm-total snowfall loads directly, and would be the better input for those criteria.
- **Report averages.** The land-wide statistics in TR-26-5 are unweighted grid-cell means, which over-weight high latitudes on a lat/lon grid. For example, the share of hours with WCT ≤ −65 °F is 7.66% by pixel mean but 5.87% area-weighted.

---

*All numbers above can be reproduced with the scripts in this repository. The independent re-verification (12 October 2026) is in `verification/`, which holds the method, per-day tables, figures and scripts. Earlier checks are in `eda/`, `preprocess/` (step 5 and step 8 validation reports) and `eda/scripts/check_atlas_min.py`. Contact SNAP for the code or the recomputed coverages.*
