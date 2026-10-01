# AZCOT
Exploration and processing of the Arctic and Subarctic Zonal Characterization and Operational Thresholding (AZCOT) dataset

https://erdc-library.erdc.dren.mil/entities/publication/52139a60-047d-4af5-bcd0-676122c082d3  
https://erdc-library.erdc.dren.mil/entities/publication/eeed3128-7f82-4d7d-bf3b-a4f02954f1aa  


## Project overview

AZCOT builds a 30-year (1991–2020) climatological atlas of cold-season weather conditions, used to define "operational thresholds" for when conditions become hazardous. The source data covers only the cold-season months (October through March) across a set of meteorological variables derived from hourly ERA5 data.

The dataset lives at `/beegfs/SNAP/rltorgerson/AZCOT` and is split across two subdirectories, `disk1` and `disk2`, each documented by its own `README.docx`.

## disk1 — raw data and computed statistics

- `data/{month}/{day}/` — hourly GRIB/NetCDF files named `YYMMDDHH.VARIABLE.{grib,nc}` (YY = year, MM = month, DD = day, HH = hour), plus 30-year climatological files named `VARIABLE.monthDDHH.91-20clim.nc`. Variables include `2T` (2m air temp), `SKT` (skin temp), `STL1` (soil temp), `SD` (snow depth), `SWE` (snow water equivalent), `10U`/`10V` (wind components), `WD10`/`WS10_knots` (wind direction/speed, derived), `WCT` (wind chill, derived), and an unlabeled parameter `var29`.
- `Metrics/{time interval}_{variable}_stats/{month}_{time interval}_{variable}_stats.nc` — each file holds the min/max, average, and frequency/duration of extreme events for a variable within a given time interval.
- `METAR Analysis/` — yearly daily averages derived from METAR station observations, used as a separate validation/comparison dataset against the reanalysis-derived fields.

## disk2 — map atlas and production app

- `Atlas/{month}/{time interval}/{variable}/{metric}/{month}_{time interval}_{variable}_{metric}.*` — the finished PDF map products. Quadrant maps append the quadrant (`BottomLeft`, `BottomRight`, `TopLeft`, `TopRight`) to the filename.
  - **Time interval**: `Six Hour` (static six-hour intervals per day — `{day}_6h_{hour1}through{hour2}`), `Daily` (`{day}`), `Weekly`/`Biweekly` (`{day1}through{day2}`), `Monthly` (full month). The whole Oct–Mar period is `OctThroughMar`.
  - **Variable**: 2m air temperature (`2T`), skin/surface temperature (`SKT`), wind-chill temperature (`WCT`), soil level 1 temperature (`STL1`), wind speed (`WSPD`), wind direction (`WDIR`), snow depth (`SD`), snow load (`SL`).
  - **Metric**: `Average` (30-year average), `Maximum`/`Minimum` (highest/lowest hourly value within the interval, maximized/minimized across the 30 years — not available for wind direction), `Frequency` (fraction of hours exceeding a threshold over the 30-year period — not available for wind direction), `Consecutive` (average length of extreme events, in hours, averaged across the 30-year period — not available for Six Hour intervals, or for snow load, snow depth, wind direction, or soil temperature).
  - `zYear/` — whole Oct–Mar period maps for every variable/metric combination, plus snow-load "First Exceedance" maps (`sl_first_exceedance_day_{thresholdValue}.pdf`, threshold in lbs/ft²).
  - `zScripts/` — the production pipeline: `metricCalculation_frequency.py` and `metricCalculation_consecutive.py` (NetCDF → statistics), and two Jupyter notebooks — `AZCOT_Maps.ipynb` (ArcGIS Pro setup, example metric calculations, map-creation walkthrough, debugging scripts) and `AZCOT_Map_Creation.ipynb` (the full NetCDF → TIFF → ArcGIS layer → PDF pipeline, organized Metric > Time Interval > Variable) — plus the supporting `.aprx` ArcGIS project files, layer templates, and map design files.
- `App/` — a deployed ArcGIS Pro tool (`mapUI.py` / `mapUI.aprx`) with a working geodatabase (`tempRaster.gdb`), a simplified interactive viewer built from the atlas outputs.
- `Archive/` — older/intermediate versions of the data and maps (`zDecadal`, `zPercentiles`, `zUnclipped`, `oldData`).

## Directory stats

Sizes below are **apparent (uncompressed) size**, measured with `du --apparent-size`. The underlying BeeGFS filesystem transparently compresses data at rest, so a plain `du -sh` undercounts true size dramatically — e.g. `disk1/data` showed as 7.8 G on-disk but is actually 1.4 T of uncompressed data (~180x compression), and `disk2/Archive` showed as 192 G on-disk but is actually 768 G uncompressed (~4x). File counts are unaffected by compression.

| Path | Apparent size | On-disk (compressed) | File count | Notes |
|---|---|---|---|---|
| `disk1/data` | 1.4 T | 7.8 G | 1,755,202 | 798,448 GRIB + 956,754 NetCDF |
| `disk1/Metrics` | 98 G | 7.1 G | 4,941 | computed stats (.nc) |
| `disk1/METAR Analysis` | 26 G | 70 M | 21,872 | station-derived yearly averages |
| `disk2/Atlas` | 459 G | 1.8 G | 848,740 | finished PDF maps |
| `disk2/Archive` | 768 G | 192 G | 1,214,582 | older/intermediate data & maps |
| `disk2/App` | 8.9 M | 110 K | 79 | ArcGIS mini-app + geodatabase |
| **Total** | **~2.75 T** | **~209 G** | **~3,845,000** | |

`disk1/data` file counts by variable (hourly + climatology files combined):

| Variable | GRIB files | NetCDF files |
|---|---|---|
| 2T | 131,232 | 131,232 |
| SKT | 131,232 | 131,232 |
| STL1 | 131,232 | 131,232 |
| 10U | 131,232 | — |
| 10V | 131,232 | — |
| SWE | 131,232 | — |
| var29 (unlabeled) | 11,056 | 11,056 |
| SD | — | 131,232 |
| WD10 | — | 131,232 |
| WS10_knots | — | 131,232 |
| WCT | — | 131,294 |

## GRIB vs. NetCDF: same data, different format

Three variables (`2T`, `SKT`, and `STL1`) exist as both `.grib` and `.nc` files sharing the same basename (e.g. `00010100.2T.grib` / `00010100.2T.nc`). These were checked directly with `cdo diffv` (CDO 2.0.5) across two independent dates (2000-01-01 and 2000-03-15): the comparison reported **zero differing values**, and `cdo info -timmean` showed identical minimum/mean/maximum (222.13 / 254.27 / 281.87 K for 2T on 2000-01-01) and identical grid (1440×121, -180 to 179.75°E, 90 to 60°N) between the two formats. The `.nc` files are straightforward NetCDF conversions of the same GRIB records, and not independently derived data.

The remaining variables exist in only one format, because they aren't raw/converted pairs at all:

- **GRIB-only**: `10U`, `10V`, `SWE` — raw ERA5 inputs that were never converted to NetCDF.
- **NetCDF-only**: `SD`, `WCT`, `WD10`, `WS10_knots` — derived/computed variables that were only ever written as NetCDF (e.g. `WCT` is wind chill computed from `2T` and wind speed; `WD10`/`WS10_knots` are wind direction/speed computed from the `10U`/`10V` components).
