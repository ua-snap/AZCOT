# AZCOT: scoping the next phase

This outlines three levels of effort for turning the AZCOT work into usable products. Each level includes everything in the levels below it. The guiding aim is the most interpretive value from pairing ERA5 with the specification tables in the military documents (TR-26-5, ATP 3-90.96, MIL-HDBK-310, AR 70-38), without research-grade modeling such as lake and river ice thickness.

| | Level 1: as is | Level 2: mine AZCOT fully + snowfall | Level 3: fill gaps with more ERA5 data |
|---|---|---|---|
| New ERA5 data | none | 1 hourly variable (snowfall) | 12 more hourly variables |
| Table rows answered: fully / at least partly* | 70% / 89% | 72% / 90% (also gains in accuracy: exact frostbite, joint stoplight, gusts) | ~76% / ~96% (proxies flagged) |
| Claude active hours (this level / cumulative) | 2–4 / 2–4 | 8–13 / 10–17 | 10–18 / 20–35 |
| Wall-clock time | 1–2 days | ~1 week | ~2 weeks |
| New storage | ~5–10 GB (Rasdaman copy) | +4–7 GB processed; raw snowfall ~45 GB if kept | +10–15 GB processed; raw ERA5 ~0.55 TB if kept, ~50–100 GB peak if processed and deleted year by year |

\* *Counted from the 178 rows of [`site_characterization/thresholds.csv`](site_characterization/thresholds.csv).*
- *"Fully" means every input the row needs is available.*
- *"Partly" means some inputs are missing. Most of these are the 33 stoplight rows from TR-26-5 Table 6, which also need ceiling, visibility, turbulence or icing. Visibility and turbulence are not in ERA5, so those rows stay partial at every level.*
- *The Level 3 figures are projections.*

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

- Rasdaman ingest recipes for three kinds of coverage:
  - the 3-D time × lat × lon coverages;
  - the 4-D histogram and stats coverages, which add a threshold, bin or percentile axis;
  - the separate snow-depth grid.
- Possibly adjusting the climatological time axis (nominal dates) to suit Rasdaman.
- Testing representative WCPS queries: point value, area summary, share of hours beyond a limit.
- Documentation.

The intermediates (2.4 GB) can be deleted once ingested.

**Effort:** 2–4 h of Claude time plus Rasdaman administration. **Storage:** the existing 4.1 GB, plus Rasdaman's internal copy (~4–8 GB).

---

## Level 2: extract everything AZCOT already contains, plus hourly snowfall

The raw AZCOT hourly files (1.4 TB) hold more than the current coverages use. Level 2 processes them further, adds one ERA5 variable (hourly snowfall) to close the tent and shelter snow-load gap, and adds an app-style query layer.

| Product | Source | Tables it serves | Est. hours |
|---|---|---|---|
| **Exact frostbite danger classes**: hourly time-to-frostbite from air temperature and wind (TR-26-5 Eq. 5), classified green / amber / red; replaces the wind-chill approximation in maps and site pages | raw 2T + WS10 | TR-26-5 T4–T5 | 1.5–2 |
| **Joint stoplight categories**: per-hour favorable / marginal / unfavorable for operations limited by both wind *and* temperature (Gray Eagle, personnel), instead of each separately | raw 2T + WS10 | TR-26-5 T6 | 1–1.5 |
| **Partial gust climatology** from `var29` (ERA5 instantaneous gust, 06 and 18 UTC only), flagged as a lower bound on peak gusts | raw `var29` | T6 wind limits, 100 mph structure rating | ~1 |
| **Equipment suitability layers** for all minimum-temperature items (first and last usable month, share of hours below the limit) | t2 histograms | TR-26-5 T9–T30 | ~1 |
| **Lunar illumination and elevation** (astronomical calculation, no data) | computed | T6 illumination | 0.5–1 |
| **App-backend proof of concept**: the site characterization re-pointed to query Rasdaman (WCPS) instead of local files, so any clicked coordinate works | Level 1 Rasdaman | all | 1–2 |
| **24-hour and storm-total snowfall loads**: rolling 24-hour and storm sums of hourly snowfall (water equivalent × 204.7 → lb/ft²), as coverages, maps and site-page verdicts | ERA5 hourly snowfall (`sf`), sourced from existing SNAP ERA5 holdings if available, otherwise from Copernicus (~45 GB) | TR-26-5 §1 tentage 10 lb/ft², rigid shelters 20 lb/ft² | 2–3 |
| Updates to docs, plots, site pages and validation | — | — | ~1 |

**Effort:** 8–13 h of Claude time (cumulative 10–17 h). Each raw pass is a 30–60 min SLURM job. **Storage:** +4–7 GB of coverages, plus ~45 GB of raw snowfall if kept.

**Still open after Level 2:** full hourly gusts; precipitation and wet-cold bands; ceiling; snow density and snowfall-rate categories; frost depth; pressure. All of these need more ERA5 data.

---

## Level 3: add the remaining ERA5 variables and fill the gaps

Download hourly ERA5 single-level fields for 60–90 °N, October–March, 1991–2020, and process each with the existing pipeline machinery (true extremes, Feb 29 dropped, monthly histograms, validation).

| ERA5 variable (short name) | New products | Tables it serves |
|---|---|---|
| 10 m wind gust, hourly (`10fg`) | **Hourly gust climatology**; gust parts of the stoplight; 100 mph structure check; blizzard frequency (gust ≥ 35 mph with snowfall) | TR-26-5 T6, §1; ATP 1-6 |
| Total precipitation (`tp`), precipitation type (`ptype`) | **Precipitation intensity and type frequencies**; stoplight precipitation categories; **wet-cold occurrence** for the ECWC wet bands; **freezing-rain frequency** as an icing screen; rain-on-snow | TR-26-5 T6–T8; MIL-HDBK-310 §5.1.14 |
| Cloud base height (`cbh`), low cloud cover (`lcc`) | **Ceiling proxy** for the stoplight. ERA5 cloud base is not a formal ceiling, so this is flagged. | TR-26-5 T6 |
| Snow density (`rsn`) | **Snow density classes** as a trafficability proxy; **snowfall-rate categories** (snowfall depth per hour, from the Level 2 snowfall and density) | ATP 1-2, 1-6 |
| Soil temperature levels 2–4 (`stl2`–`stl4`); soil moisture (`swvl1`–`swvl2`) | **Frost-depth estimate**: depth of the 0 °C level across the four ERA5 soil layers (coarse), with wet/dry soil from soil moisture | ATP B-2 (vehicle crossing over soft terrain) |
| Surface pressure (`sp`) | Low pressure / air density | MIL-HDBK-310 §5.1.17–5.1.19 |
| 2 m dew point (`d2m`) | Humidity and frost-formation conditions | AR 70-38 cold cycles |

With these, almost every "not determined" row in the site pages becomes determined, or a clearly flagged proxy. The new products then flow into the maps, the equipment layers, Rasdaman and the site pages.

**Effort:**

| Task | Claude active hours |
|---|---|
| Data sourcing (existing SNAP ERA5 holdings, else CDS API; reuses the Level 2 setup) | ~0.5 |
| Per-variable reduction, coverages and validation (~9 steps) | 5–9 |
| New derived products (blizzard index, precipitation and ceiling categories, snowfall-rate categories, frost depth, density classes) | 3–5 |
| Updating the thresholds catalog, site pages, plots and docs | 2–3 |
| **Total for Level 3** | **10–18** |
| **Cumulative (Levels 1–3)** | **20–35** |

**Wall-clock time:** about **2 weeks**. Much of this ERA5 data is probably already in SNAP's holdings, in which case sourcing it is a copy or subset rather than a download. Anything that isn't comes from the Copernicus CDS, which needs a free account and API key (none is configured on this account now).

**Storage:**
- **Raw downloads:** each hourly 0.25° field for 60–90 °N is ~341 KB as 16-bit GRIB (measured on the AZCOT files), so one variable for the full period (131,760 hours) is ~45 GB. The 12 Level 3 variables are **~0.55 TB** if kept. Processing a year at a time and deleting raw files keeps the peak to **~50–100 GB**. BeeGFS also compresses transparently.
- **Processed coverages:** ~0.5–1 GB per variable, **+10–15 GB** in total.

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

**Level 2 is the best value per hour.** It adds exact frostbite classes, joint stoplight categories, the tent and shelter snowfall loads, and an app-backend proof of concept, with only one new ERA5 variable. Its gust layer is only a lower bound and should be presented that way.

**Level 3 closes most of what's left in about two weeks.** The first thing to do is check which of the 12 variables SNAP's ERA5 holdings already contain. **Hourly gusts** should come first, since they drive the stoplight and structure limits.

*Prepared October 2026. Estimates assume Claude Opus at high effort, working in this repository with the existing pipeline.*
