# Storm definition for the rigid-shelter snow load

The storm-total snowfall load (`storm_*` variables) depends on a definition of "storm" that **we chose**; TR-26-5 doesn't give one. This page explains why a definition is needed, what it is, the evidence behind it, how much it matters, and how to change it.

| File | What it is |
|---|---|
| `README.md` | this page |
| [`sensitivity.md`](sensitivity.md) | sensitivity results at nine sites (generated; do not edit) |
| `extract_site_snowfall.py`, `.slurm` | pulls hourly ERA5 snowfall at the sites to `<OUT_ROOT>/storm_definition/sf_sites.nc` (~15 min on SLURM) |
| `storm_sensitivity.py` | runs step 10's own storm code for every definition tested and writes `sensitivity.md` (~1 min) |

## Why a definition is needed

TR-26-5 §1 (snow-load design criteria) gives two loads that come from falling snow, not from the snowpack:

> Portable equipment, such as tentage is based on 24 hour snowfalls withstanding a max snow load value of 10 lb/ft² … Temporary equipment such as rigid shelters, portable hangars, and so forth is based snowfalls associated with storms lasting longer than one day and is required to withstand a snow load value of 20 lb/ft² … This equipment should be cleared of snow between storms.

- **The tentage load is a fixed window** (24 hours), so it can be computed directly from hourly snowfall.
- **The rigid-shelter load is the snow from one storm.** The shelter is cleared between storms, so the load that matters is everything that falls from one clearing to the next. ERA5 gives a continuous series of hourly snowfall amounts with no storm labels, including light "drizzle" hours, lulls inside a storm, and systems that follow each other closely.

To add up "one storm" we must decide (a) what counts as a snowing hour and (b) how long a lull ends a storm. The report specifies neither, and it gives no reference that does.

## The definition used

Implemented in [`step10_reduce_snowfall.py`](../step10_reduce_snowfall.py) (`WET_MM_H`, `GAP_H`, function `loads()`):

1. **Wet hour:** ERA5 hourly snowfall ≥ **0.1 mm water equivalent**, which is 0.02 lb/ft², or about 1 mm of new snow at a specific gravity of 0.1. Lighter hours count as dry.
2. **Storm:** a run of wet hours in which **no dry gap is longer than 12 hours**. A dry spell of 13 hours or more ends the storm.
3. **Storm total:** all snowfall from the storm's first wet hour to its last, including any light hours in between, × 204.724 lb/ft² per m w.e. (TR-26-5 eq. 4, the same factor as AZCOT's snow load).
4. **Timing:** a storm is credited to the calendar day on which it **ends**, when the shelter carries its full load. A storm still running at the end of the season (Mar 31, or Dec 31 2020) is credited to that day with its full total, read from the April or January data. Storms that started in September count in October.
5. **Every storm counts, however short.** The report frames the criterion around storms "lasting longer than one day". A shorter storm still loads the shelter, though, and dropping storms under 24 h could only lower the record. So no duration filter is applied. Durations are kept (`storm_hours` in the step-10 intermediates) if one is wanted later.

**Why 12 hours.** "Cleared of snow between storms" needs a lull long enough to clear the shelter, and half a day of no snow is a reasonable reading of that. The sensitivity test supports it as the middle option:
- **6 h** splits events that are plainly one storm. At Fairbanks the record drops from 7.8 to 5.3 lb/ft², and the longest storm from 2.6 to 1.3 days.
- **24 h** chains successive systems in snowy maritime climates into month-long "storms": 33 days at Valdez, 21 days at Tromsø. That is seasonal accumulation, which TR-26-5 covers with the separate 48 lb/ft² semipermanent-structure criterion.

**Why 0.1 mm/h.** ERA5 produces many hours of trace snowfall. A lower threshold (0.05) lets those trace hours bridge gaps; a higher one (0.2) cuts real light snow out of storms. At the gap used, 0.1 sits between them (see [sensitivity.md](sensitivity.md)).

## How much it matters

Selected rows from [sensitivity.md](sensitivity.md) (wet = 0.1 mm/h; lb/ft²; Oct–Mar 1991–2020):

| Site | Record 72 h (no definition) | Record storm, gap 6 h | **Record storm, gap 12 h (used)** | Record storm, gap 24 h | Longest storm, gap 12 h |
|---|---:|---:|---:|---:|---:|
| Fairbanks | 7.9 | 5.3 | **7.8** | 8.6 | 2.6 days |
| Utqiagvik | 5.1 | 5.0 | **5.1** | 5.1 | 3.8 days |
| Eureka | 3.0 | 2.6 | **2.6** | 2.6 | 1.3 days |
| Pituffik | 9.7 | 9.7 | **10.5** | 10.5 | 5.4 days |
| Norilsk | 7.9 | 13.9 | **13.9** | 22.8 | 9.8 days |
| Tromsø | 12.9 | 14.9 | **30.9** | 36.8 | 12.8 days |
| Valdez | 48.5 | 59.4 | **61.5** | 109.2 | 15.3 days |

- **Dry and interior climates** (most of the Arctic): the definition barely matters. Storm totals stay far below 20 lb/ft² under any choice.
- **Snowy maritime climates:** the definition matters a lot, and **it can change a verdict.** Tromsø's shelter verdict is *caution* with the 12 h gap: 20 lb/ft² was reached in 4 of 30 years, and in no single month in more than 2 of 30, but would be *OK* with 6 h. Norilsk is *OK* with 6 or 12 h but would reach 20 lb/ft² once with 24 h.
- **Grid-wide** with the definition used: 4.4% of seasonal land ever had a storm total ≥ 20 lb/ft² in 30 winters (step 12 report). We have not rerun the whole grid with other definitions (see "Changing it").

## Limitations

- **Long maritime "storms".** Even with a 12 h gap, Tromsø's record storm lasted 12.8 days and Valdez's 15.3 days. Where snow falls on most days, a series of systems with short breaks counts as one storm. The totals there are best read as "snow between half-day lulls". Compare them with the 72-hour load (`sf72_max`), which is lower (Tromsø 12.9, Valdez 48.5).
- **Snowfall only.** No wind redistribution (drifting onto or off a roof), melt, sublimation, rain-on-snow loading, or compaction; a flat surface; 0.25° grid cells (about 28 km).
- **ERA5 snowfall is a model forecast field**, not observed. Heavy-snowfall extremes in steep coastal terrain are likely underestimated at 0.25°.
- **The 30-year record is a short sample** for a design load. `storm_ge20_years` (share of years reaching the load) is the more stable number to plan with.

## Where it is used

- **Coverages** (`azcot_snowfall_{daily,monthly,seasonal}.nc`): `storm_max`, `storm_mean_annual_max`, `storm_ge20_years`, `storm_ge20_per_year`; histograms in `azcot_snowfall_histogram_monthly.nc` (`storm_counts`). The definition is stored in each file's `summary` and in the `comment` of every storm variable. The 72-hour load (`sf72_*`) needs no definition and is there as a cross-check.
- **Site pages** ([site_characterization/](../../site_characterization/README.md)): the rigid-shelter row (SLa/SLb in `thresholds.csv`) uses `storm_max` and `storm_ge20_years`. OK means the load was never reached in 30 years; caution, at most 1 year in 10; no, more often.
- **Maps** ([plots/plots.md](../../plots/plots.md) §3b).

## Changing it

1. Edit `WET_MM_H` and/or `GAP_H` at the top of [`step10_reduce_snowfall.py`](../step10_reduce_snowfall.py).
2. Move or delete `intermediate/snowfall/` (step 10 skips winters that already exist), then run `sbatch step10_reduce_snowfall.slurm` (~22 min) followed by `sbatch steps11to12.slurm snowfall` (~10 min). Step 11 refuses to mix winters built with different parameters.
3. Regenerate the site pages (`site_characterization/scripts/characterize.py`), the plots (`make_plots.py snowfall_design snowfall_storm_monthly`) and `python storm_sensitivity.py` (it marks the definition in use).

To compare definitions grid-wide without overwriting anything, set `AZCOT_PRE_OUT` to a scratch root for the step 10–11 run. Step 11 also needs `intermediate/surface_type.nc` there.
