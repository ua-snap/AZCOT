# AZCOT: scoping next steps

## Work completed so far

We independently checked the AZCOT dataset (ERDC/CRREL) against its own raw hourly ERA5 files and found it largely sound, with several significant errors in the pre-computed `Metrics`. These are documented, with evidence, in an [author-facing issues report](AZCOT_DATA_ISSUES.md):
- the "minimum" fields are averages of yearly lows rather than record lows;
- metrics for Feb 29 (leap day) were computed incorrectly;
- air temperature is stored in kelvin while its thresholds are in °F, so every air-temperature frequency is zero;
- wind chill is computed from skin temperature rather than 2 m air temperature, which makes it colder (found 9 Oct 2026);
- snow-depth hours are missing systematically;
- the Atlas air-temperature "lowest recorded" maps are too warm.

We then built a validated preprocessing pipeline ([preprocess/](preprocess/README.md)). Its output is 24 CF-compliant NetCDF coverages for wind chill, snow load, air temperature, wind speed and snow depth (1991–2020, Oct–Mar), with glacier cells flagged. Validation reproduces the published TR-26-5 numbers.

The pipeline works from the raw hourly files rather than `Metrics` wherever `Metrics` is wrong, so the coverages are free of the issues above, except the snow-depth gaps and the skin-temperature wind chill:

| Issue | Status in our coverages |
|---|---|
| "Minimum" fields are averages of yearly lows | **Fixed.** True minimum, mean and maximum recomputed from all 720 hourly values per day, for every variable. |
| Feb 29 computed incorrectly | **Fixed.** Feb 29 dropped (182-day calendar). |
| Air temperature in kelvin with °F thresholds | **Fixed.** Converted to °F at the source. Frequencies come from our own hourly histograms; `Metrics` air-temperature statistics are not used. |
| Wind chill computed from skin temperature, not 2 m air temperature | **Not fixed.** The WCT coverages keep AZCOT's definition. The Level 2 frostbite classes use 2 m air temperature. Fixing WCT means recomputing it from 2T and wind (about one more SLURM pass). |
| `Metrics` `max_WSPD` is a copy of `min_WS10` | **Fixed.** Wind maximums recomputed from the hourly data. (*Correction, 9 Oct 2026:* we had also reported the wind files as m/s rather than knots. That was our error; they are knots. Our wind coverages had been converted twice and were 1.94× too high; they have been rebuilt.) |
| Missing snow-depth hours | **Worked around, not fixed.** Missing hours are skipped and recorded, and statistics use only the hours that exist. The last day of each month therefore rests on 30 values instead of 720. Fixing it needs the data re-downloaded. |
| Atlas air-temperature "lowest recorded" maps too warm | **Replaced, not corrected.** The Atlas rasters are untouched, but our true record lows (`t2_min`) can stand in for them. |

Two lesser problems are fixed as well:
- **Metadata:** the coverages carry units, a CRS and provenance.
- **Snow load over ice:** the ERA5 glacier cap (2047 lb/ft²) is flagged, so it can't be mistaken for a real load.

On top of the coverages are:
- the initial [exploratory analysis](eda/EDA.md);
- [18 maps and charts](plots/plots.md), including approximate frostbite-danger maps and the recommended glacier symbology;
- a [site-characterization proof of concept](site_characterization/README.md). It checks every condition-to-equipment table in TR-26-5, ATP 3-90.96, MIL-HDBK-310 and AR 70-38 against the climatology of any point, and produces a one-page "OK / caution / no" shopping list with a [data-gap inventory](site_characterization/data_gaps.md).

Two supporting checks inform the plan below:
- **Snow load:** a review confirmed that AZCOT computes it correctly from SWE, but that 24-hour (tent) and storm (rigid-shelter) loads need ERA5 hourly snowfall.
- **CASC / SNAP's ERA5 holdings:** an inventory found that hourly snowfall and precipitation are already available locally.

### Source documents

All are in [`docs/`](docs/); their extracted text is in `eda/reference/` and `site_characterization/reference/`.

| Document | Title | Date | How we use it |
|---|---|---|---|
| [ERDC/CRREL TR-26-5](docs/ERDC-CRREL%20TR-26-5.pdf) | *Arctic and Subarctic Zonal Characterization and Operational Thresholding (AZCOT)* | March 2026 | Main AZCOT report; Tables 1–30 (cold zones, frostbite, stoplight, clothing and equipment limits); snow-load design criteria |
| [ERDC/CRREL SR-25-2](docs/ERDC-CRREL%20SR-25-2.pdf) | *Development and Management of Arctic Zonal Characterization Products Geospatial Database* | October 2025 | How the AZCOT metrics and Atlas were produced |
| [ATP 3-90.96 / MCTP 12-10E](docs/ARN46141-ATP_3-90.96-002-WEB-5.pdf) | *Arctic and Extreme Cold Weather Operations* | February 2025 (incl. Change 2, March 2026) | Cold temperature zones, snow and vehicle tables, ice capacity, safety recommendations per zone |
| [MIL-HDBK-310](docs/MIL-HDBK-310.pdf) | *Global Climatic Data for Developing Military Products* | 23 June 1997 | 1%-of-hours design convention; low temperature, snow load, ice accretion, freeze–thaw |
| [AR 70-38](docs/AR%2070-38.pdf) | *Research, Development, Test and Evaluation of Materiel for Worldwide Use* | 26 June 2020 | Climatic design types (C1–C4) |
| [ATP 4-33](docs/ATP-4-33-Maints-Ops-July-2019.pdf) | *Maintenance Operations* | July 2019 | Reviewed; no condition-to-equipment tables (its cold-weather limits reach TR-26-5 via TM 4-33.31) |

## Future work

### Progress (9 October 2026)

| Item | Status |
|---|---|
| **Level 1:** Rasdaman recipes | ✅ **Drafted, not ingested.** [rasdaman/](rasdaman/README.md) has 39 recipes (house style), a prep script and acceptance queries with expected answers. Ingesting is on hold by decision. Rasdaman would need 17.3 GB uncompressed, more than the 4–8 GB estimated below. |
| **Level 2:** exact frostbite classes | ✅ **Done and validated.** TR-26-5 Eq. 5 is applied to every hour of air temperature and wind; maps, site pages and the frostbite plots now use it. |
| **Level 2:** 24-hour and storm snowfall loads | ✅ **Done and validated.** Uses SNAP ERA5 hourly snowfall. Only 2.8% of seasonal land ever reached 10 lb/ft² in 24 h (tentage), and 4.4% a 20 lb/ft² storm (rigid shelters). The storm definition (dry gaps ≤ 12 h) is our choice, documented with its sensitivity in [preprocess/storm_definition/](preprocess/storm_definition/README.md). |
| **Level 2:** precipitation products, joint stoplight, partial gusts, equipment layers, lunar, app backend | Deferred. |
| Found along the way | Our wind coverages were 1.94× too high (the raw files are knots, not m/s); fixed and rebuilt. AZCOT wind chill is computed from skin temperature (data-issues report, issue 10); not fixed in the WCT coverages. |

✅ = done, ◐ = partly done. SLURM time for the Level 2 passes: step 9 7 min, step 10 22 min, steps 11–12 11 min, plus the 15 min wind rerun.

### The three levels

This outlines three levels of effort for turning the AZCOT work into usable products. Each level includes everything in the levels below it. The guiding aim is the most interpretive value from pairing ERA5 with the specification tables in the military documents (TR-26-5, ATP 3-90.96, MIL-HDBK-310, AR 70-38), without research-grade modeling such as lake and river ice thickness.

| | Level 1: as is | Level 2: mine AZCOT + SNAP's ERA5 holdings | Level 3: fill gaps with downloaded ERA5 |
|---|---|---|---|
| New ERA5 data | none | snowfall + total precipitation, **already on our system** (no download) | dew point (on our system) + **11 variables to download** |
| Table rows answered: fully / at least partly* | 70% / 89% | ~74% / ~94% (also gains in accuracy: exact frostbite, joint stoplight, gusts) | ~76% / ~96% (proxies flagged) |
| Claude active hours (this level / cumulative) | 2–4 / 2–4 | 9–14 / 11–18 | 8–16 / 19–34 |
| Wall-clock time | 1–2 days | ~1 week | ~2 weeks |
| New storage | ~5–10 GB (Rasdaman copy) | +5–8 GB processed (ERA5 read in place, no raw copy) | +8–12 GB processed; raw downloads ~0.5 TB if kept, ~50–100 GB peak if processed and deleted year by year |

\* *Counted from the 178 rows of [`site_characterization/thresholds.csv`](site_characterization/thresholds.csv).*
- *"Fully" means every input the row needs is available.*
- *"Partly" means some inputs are missing. Most of these are the 33 stoplight rows from TR-26-5 Table 6, which also need ceiling, visibility, turbulence or icing. Visibility and turbulence are not in ERA5, so those rows stay partial at every level.*
- *The Level 2 and Level 3 figures are projections.*

**How the hours were estimated.** All AZCOT work to date took about **6 hours of active Claude time** (Opus, high effort) over about 13 hours of wall-clock time across three sessions. The difference is waiting on SLURM jobs and on human review. That covered:
- the EDA;
- two rounds of preprocessing (5 variables, 24 coverages, validated);
- 18 plots;
- the site characterization proof of concept;
- the data-issues document and the snow-load review.

From that, the working rates are:

| Task | Claude active time | Wall-clock time |
|---|---|---|
| New raw-data variable, through to a validated coverage | 1–1.5 h | 2–3 h (includes a 30–60 min SLURM pass) |
| New product family (maps + doc section) | 0.5–1 h | — |
| New rule family in the site characterization | ~0.5 h | — |

Treat the estimates as ±50%. They exclude human review and Rasdaman administration.

---

### SNAP's existing ERA5 holdings

`/import/AKCASC/data/cds/reanalysis-era5-single-levels` (read-only; owned by the AKCASC group) holds **global, hourly, 0.25°** ERA5 single-level fields:
- **Layout:** one NetCDF file per variable and month.
- **Formats:** two CDS formats: classic NetCDF with 16-bit packing, and NetCDF-4.
- **Coverage:** most variables start in 1940–1959 and run to 2023–2026.
- **Same ERA5 as AZCOT:** air temperature (`t2m`) matches the AZCOT raw 2T exactly at a spot check, so the two can be used interchangeably.

Checked against the 180 AZCOT months (1991–2020, Oct–Mar):

| Variable | Availability for 1991–2020 Oct–Mar | Use in this plan |
|---|---|---|
| `sf` snowfall | complete, hourly | **Level 2:** 24-hour and storm snowfall loads (no download needed) |
| `tp` total precipitation | complete, hourly | **Level 2:** precipitation intensity; rain vs. snow (`tp` − `sf`); wet-cold bands; freezing-rain proxy |
| `d2m` 2 m dew point | complete, hourly | **Level 3:** humidity / frost formation (no download needed) |
| `msl` mean sea-level pressure (+ invariant geopotential in `reanalysis-era5-invariants`) | complete, hourly | Level 3 fallback: surface-pressure proxy if `sp` isn't downloaded |
| `tcc` total cloud cover | 2000–2009 **not readable** with our permissions | weak cloud proxy only; a ceiling needs cloud base height (`cbh`) |
| `t2m`, `u10`, `v10`, `sd` | complete, hourly | same as the AZCOT inputs; would let the climatology be updated past 2020 (e.g. a 1994–2023 normal) |
| `skt` | daily (00 UTC) only | not needed (AZCOT has hourly SKT) |
| `cp`, `lsp`, `pev`, `slhf`, `sshf`, `ssr`, `ssrd`, `str`, `fdir`, `tcrw`, `sst`, `swvl3`, `swvl4` | various; `sst` is 2024 only; `tcrw` has gaps; `swvl3`/`swvl4` are not readable | not used by the specification tables |

**Not on the system** (sibling directories hold only ERA5-Land snow depth, geopotential and a few pressure-level fields): hourly 10 m gust (`10fg`), precipitation type (`ptype`), cloud base height (`cbh`), low cloud cover (`lcc`), snow density (`rsn`), soil temperature levels 2–4 (`stl2`–`stl4`), soil moisture levels 1–2 (`swvl1`–`swvl2`), and surface pressure (`sp`). These 11 are Level 3's downloads.

Before Level 2 and 3 start, ask the data owner for group read access to `tcc` 2000–2009 and to `swvl3`/`swvl4`.

---

## Level 1: leave the pipeline as is, ingest into Rasdaman

### What we have

24 validated, CF-compliant NetCDF coverages (4.1 GB) in `/beegfs/CMIP6/jdpaul3/azcot_preprocess/coverages`. They cover 1991–2020, October–March, with Feb 29 dropped, on the 0.25° ERA5 grid (60–90 °N); snow depth is on the 0.1° ERA5-Land grid.

| Variable | Climatology (daily / monthly / seasonal) | Other |
|---|---|---|
| Wind chill | true min, mean, max | frequency, consecutive-hour and percentile stats |
| Snow load | true min, mean, max | frequency and percentile stats; NaN off seasonal land |
| Air temperature | true min, mean, max | freeze–thaw days; monthly 1 °F histograms |
| 10 m wind speed (hourly mean) | true min, mean, max | monthly 1 kn histograms |
| Snow depth | true min, mean, max | monthly 1 in histograms |
| All 0.25° files | — | `surface_type` flag (ocean / land / glacier / perennial snow), CRS, provenance |

The histograms answer "what share of hours is beyond **any** limit", e.g. an equipment rating of −53 °F. That is what makes a pick-a-point "menu" possible.

The repository also holds the [EDA](eda/EDA.md), the [plots](plots/plots.md), the [site characterization proof of concept](site_characterization/README.md) and the [data-issues report](AZCOT_DATA_ISSUES.md).

### Questions Level 1 can already answer, for any grid cell or region

- **Cold:** which ATP 3-90.96 cold zone applies (typical, design-1%, or record), which AR 70-38 climatic design type (C1–C4), and the MIL-HDBK-310 1/5/10% design-cold values.
- **Equipment:** for each of ~100 items in TR-26-5 Tables 9–30 (clothing items, boots, sleeping bags, tents, batteries, electronics, generators, fuels, oils, hydraulics, greases, weapons, lubricants, aircraft), is it OK, caution, or no, and in which months?
- **Planning schedules:** which ECWC clothing configuration (dry bands) and which lubricant regime applies, and how often.
- **Frostbite:** approximate green/amber/red danger shares (from wind chill), and where the Army −65 °F requirement actually matters.
- **Snow:** vehicle type versus snow depth (TR-26-5 Table 3, ATP B-3); life-sustaining (25 lb/ft²) and semipermanent (48 lb/ft²) snow loads; when snow load arrives in the season; freeze–thaw frequency.
- **Wind:** the wind-speed part of the Combat Weather Team stoplight (TR-26-5 Table 6), from hourly-mean wind only.

### Easily revised into usable products

- **Atlas-style maps:** already generated in `plots/`. They regenerate directly from the coverages, including the glacier symbology and the frostbite approximation.
- **Equipment suitability layers:** one map per item, e.g. "months JP-8 is usable". These are a few lines each from the air-temperature histograms (≈1 h for all ~100 items).
- **Site pages:** `site_characterization/` produces a one-page "shopping list" per point.

### Work required

- ✅ Rasdaman ingest recipes for three kinds of coverage ([rasdaman/](rasdaman/README.md); drafted, not ingested):
  - the 3-D time × lat × lon coverages;
  - the 4-D histogram and stats coverages, which add a threshold, bin or percentile axis;
  - the separate snow-depth grid.
- ✅ Possibly adjusting the climatological time axis (nominal dates) to suit Rasdaman. (Done: `mmdd` and `month` axes hold real calendar values.)
- ◐ Testing representative WCPS queries: point value, area summary, share of hours beyond a limit. (Queries and expected answers are written in `rasdaman/test_wcps.py`; they run once the coverages are ingested.)
- ✅ Documentation.

The intermediates (2.4 GB) can be deleted once ingested.

**Effort:** 2–4 h of Claude time plus Rasdaman administration. **Storage:** the existing 4.1 GB, plus Rasdaman's internal copy (~4–8 GB). *Measured when the recipes were drafted: 15.3 GB uncompressed for these coverages, 17.3 GB with Level 2.*

---

## Level 2: mine AZCOT and SNAP's ERA5 holdings (no downloads)

The raw AZCOT hourly files (1.4 TB) hold more than the current coverages use. Level 2 processes them further and adds two variables already on our system: ERA5 hourly **snowfall** and **total precipitation**, read in place. Together they close the tent and shelter snow-load gap and the precipitation and wet-cold gaps. Level 2 also adds an app-style query layer.

| Product | Source | Tables it serves | Est. hours |
|---|---|---|---|
| ✅ **Exact frostbite danger classes**: hourly time-to-frostbite from air temperature and wind (TR-26-5 Eq. 5), classified green / amber / red; replaces the wind-chill approximation in maps and site pages | raw 2T + WS10 | TR-26-5 T4–T5 | 1.5–2 |
| ✅ **24-hour and storm-total snowfall loads**: rolling 24-hour and storm sums of hourly snowfall (water equivalent × 204.7 → lb/ft²), as coverages, maps and site-page verdicts | SNAP ERA5 hourly snowfall (`sf`), complete for 1991–2020 | TR-26-5 §1 tentage 10 lb/ft², rigid shelters 20 lb/ft² | 1.5–2.5 |
| **Precipitation products**: hourly intensity frequencies (stoplight light / medium / heavy); liquid vs. frozen share (`tp` − `sf`); **wet-cold occurrence** for the ECWC wet clothing bands; rain-on-snow; a **freezing-rain screen** (liquid precipitation with air temperature ≤ 32 °F), flagged as a proxy until precipitation type is added in Level 3 | SNAP ERA5 `tp` + `sf`, raw 2T | TR-26-5 T6–T8; MIL-HDBK-310 §5.1.14; ATP T1-7 | 1.5–2 |
| **Joint stoplight categories**: per-hour favorable / marginal / unfavorable for operations limited by both wind *and* temperature (Gray Eagle, personnel), instead of each separately | raw 2T + WS10 | TR-26-5 T6 | 1–1.5 |
| **Partial gust climatology** from `var29` (ERA5 instantaneous gust, 06 and 18 UTC only), flagged as a lower bound on peak gusts | raw `var29` | T6 wind limits, 100 mph structure rating | ~1 |
| **Equipment suitability layers** for all minimum-temperature items (first and last usable month, share of hours below the limit) | t2 histograms | TR-26-5 T9–T30 | ~1 |
| **Lunar illumination and elevation** (astronomical calculation, no data) | computed | T6 illumination | 0.5–1 |
| **App-backend proof of concept**: the site characterization re-pointed to query Rasdaman (WCPS) instead of local files, so any clicked coordinate works | Level 1 Rasdaman | all | 1–2 |
| ◐ Updates to docs, plots, site pages and validation (done for the two items above) | — | — | ~1 |

**Effort:** 9–14 h of Claude time (cumulative 11–18 h). Each raw pass is a 30–60 min SLURM job. The SNAP ERA5 files are global, so each pass subsets 60–90 °N on read. **Storage:** +5–8 GB of coverages. The ERA5 files are read in place; nothing is copied, and the source is never modified.

**Still open after Level 2:** full hourly gusts; true precipitation type (freezing rain is only proxied); ceiling; snow density and snowfall-rate categories; frost depth; pressure; humidity.

---

## Level 3: download the remaining ERA5 variables and fill the gaps

Dew point is already on our system. The other **11 variables are not**, and must be downloaded from the Copernicus CDS as hourly fields for 60–90 °N, October–March, 1991–2020. Each is processed with the existing pipeline machinery (true extremes, Feb 29 dropped, monthly histograms, validation).

| ERA5 variable (short name) | New products | Tables it serves |
|---|---|---|
| 10 m wind gust, hourly (`10fg`): download | **Hourly gust climatology**; gust parts of the stoplight; 100 mph structure check; blizzard frequency (gust ≥ 35 mph with snowfall) | TR-26-5 T6, §1; ATP 1-6 |
| Precipitation type (`ptype`): download | **True freezing-rain and ice-pellet frequencies**, replacing the Level 2 temperature-based proxy as the icing screen; precipitation-type split for the stoplight | TR-26-5 T6; MIL-HDBK-310 §5.1.14 |
| Cloud base height (`cbh`), low cloud cover (`lcc`): download | **Ceiling proxy** for the stoplight. ERA5 cloud base is not a formal ceiling, so this is flagged. The total cloud cover on our system can't substitute. | TR-26-5 T6 |
| Snow density (`rsn`): download | **Snow density classes** as a trafficability proxy; **snowfall-rate categories** (snowfall depth per hour, from the Level 2 snowfall and density) | ATP 1-2, 1-6 |
| Soil temperature levels 2–4 (`stl2`–`stl4`); soil moisture (`swvl1`–`swvl2`): download | **Frost-depth estimate**: depth of the 0 °C level across the four ERA5 soil layers (coarse), with wet/dry soil from soil moisture | ATP B-2 (vehicle crossing over soft terrain) |
| Surface pressure (`sp`): download (fallback: `msl` + geopotential, on our system) | Low pressure / air density | MIL-HDBK-310 §5.1.17–5.1.19 |
| 2 m dew point (`d2m`): **on our system** | Humidity and frost-formation conditions | AR 70-38 cold cycles |

With these, almost every "not determined" row in the site pages becomes determined, or a clearly flagged proxy. The new products then flow into the maps, the equipment layers, Rasdaman and the site pages.

**Effort:**

| Task | Claude active hours |
|---|---|
| CDS download set-up and orchestration (account + API key needed; none configured now) | ~1 |
| Per-variable reduction, coverages and validation (~9 steps) | 5–8 |
| New derived products (blizzard index, freezing-rain and ceiling categories, snowfall-rate categories, frost depth, density classes) | 2.5–4.5 |
| Updating the thresholds catalog, site pages, plots and docs | 2–3 |
| **Total for Level 3** | **8–16** |
| **Cumulative (Levels 1–3)** | **19–34** |

**Wall-clock time:** about **2 weeks**, including the CDS downloads of the 11 variables. SNAP's holdings were checked (see above) and don't contain them.

**Storage:**
- **Raw downloads:** each hourly 0.25° field for 60–90 °N is ~341 KB as 16-bit GRIB (measured on the AZCOT files), so one variable for the full period (131,760 hours) is ~45 GB. The 11 downloaded variables are **~0.5 TB** if kept. Processing a year at a time and deleting raw files keeps the peak to **~50–100 GB**. BeeGFS also compresses transparently.
- **Processed coverages:** ~0.5–1 GB per variable, **+8–12 GB** in total.

### What stays out of scope even at Level 3

| Gap | Why it stays open |
|---|---|
| Visibility (stoplight; blizzards) | ERA5 has no visibility, and AZCOT's "METAR Analysis" folder holds only gridded ERA5 averages, not observations. Needs external station archives (METAR/ASOS), point-only. |
| Aviation turbulence and icing | Need upper-air data and dedicated algorithms (research-level). |
| Thunderstorms | Only a convective proxy is possible; rare in the Arctic cold season. |
| Lake and river ice capacity (ATP C-1 to C-5) | Deferred; needs ice-growth modeling. |
| Glove, mitten and LCD ratings; vegetation and terrain for skis/snowshoes and over-snow rates | Not climate data. |

---

## Recommendation

**Level 1 is nearly free and should happen regardless.** It turns existing, validated work into a queryable service.

**Level 2 is the best value per hour.** It adds exact frostbite classes, joint stoplight categories, the tent and shelter snowfall loads, precipitation and wet-cold products, and an app-backend proof of concept, all from data already on our system. Its gust layer is only a lower bound and should be presented that way.

**Level 3 closes most of what's left in about two weeks.** It's the only level that needs downloads: 11 variables not in SNAP's holdings. Set up a CDS account early, and start with **hourly gusts**, which drive the stoplight and structure limits.

*Prepared October 2026. Estimates assume Claude Opus at high effort, working in this repository with the existing pipeline.*
