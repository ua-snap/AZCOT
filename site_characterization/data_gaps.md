# What the AZCOT data can and can't decide

This lists every table in the five source documents that the site characterization uses. For each, it shows how much the current AZCOT coverages can decide and what extra data would complete it. The row-by-row detail is in [thresholds.csv](thresholds.csv).

**Sources:** ERDC/CRREL TR-26-5 (Tables 1–30), ATP 3-90.96 (Arctic operations), MIL-HDBK-310 (global climatic design data), AR 70-38 (materiel for extreme climates), ATP 4-33 (maintenance operations).

**Data in hand** (preprocessed coverages, 1991–2020, Oct–Mar, hourly ERA5):

| Variable | What it is |
|---|---|
| Air temperature (2T) | Includes monthly hourly-value histograms and freeze–thaw days |
| Wind chill | — |
| 10 m wind speed | Hourly *mean* |
| 10 m wind gust | Raw files only (`var29` = ERA5 instantaneous gust), **at 06 and 18 UTC only**; not yet in the coverages or used here |
| Snow load | Derived from SWE |
| Snow depth | ERA5-Land |
| Surface type | Ocean / land / glacier / perennial snow |

## Fully determined

These tables depend only on temperature, snow depth or snow load.

| Table(s) | What it decides | Data used |
|---|---|---|
| TR-26-5 T1 · AR 70-38 · MIL-HDBK-310 §5.1.2 | Climatic design type (C1–C4) and the 1/5/10% design-cold values | Air-temperature histogram, coldest month |
| TR-26-5 T2 · ATP 3-90.96 T1-3 · App. F | Cold temperature zone(s) and which safety tables apply | Air temperature |
| TR-26-5 T9–T30 | Minimum operating temperature for clothing items, boots, sleeping bags, equipment, tents, batteries, electronics, generators, fuels, oils, hydraulic fluids, greases, liquids, weapons, lubricants, helicopters and fixed-wing aircraft | Air-temperature record lows and histograms |
| TR-26-5 T24–T28 | Which lubricant to use when (rifle, mortar, machine gun, M249, artillery) | Air-temperature histogram |
| TR-26-5 T7–T8 (dry bands) | Which ECWC clothing configuration applies, and how often | Air-temperature histogram |
| TR-26-5 T3 · ATP 3-90.96 B-3 | Vehicle type versus snow depth | Snow-depth histogram |
| TR-26-5 §1 · MIL-HDBK-310 §5.1.13 | Life-sustaining (25 lb/ft²) and semipermanent (48 lb/ft², seasonal accumulation) structure snow loads | Snow-load record and frequencies (glacier cells marked N/A) |
| MIL-HDBK-310 §5.1.22 | Freeze–thaw cycles | Air temperature |

## Partly determined

| Table | What we can say | What's missing | Where it could come from |
|---|---|---|---|
| TR-26-5 T4–T5 frostbite danger | Approximate green / amber / red share of hours from wind chill | The joint air temperature *and* wind speed of each hour | **Already in AZCOT:** the raw hourly 2T and WS10 files. This needs one more preprocessing step, no new data. |
| TR-26-5 T6 stoplight (airborne, fixed and rotary wing, medevac, UAVs, air assault, sling loads, FARP) | Share of hours in each wind band (hourly mean wind), plus the UAV and personnel temperature bands | Gusts, cloud ceiling, visibility, precipitation type and intensity, thunderstorms, turbulence, icing, crosswind (runway heading) | Gusts: partly **already in AZCOT** (`var29`, two samples a day, which will miss most peak gusts); hourly ERA5 10 m gust (`10fg`) for complete coverage. Others: ERA5 cloud base height, precipitation type and rate; visibility and present weather from external METAR/ASOS station archives (AZCOT's `disk1/METAR Analysis` holds only gridded ERA5 daily averages, no station observations; ERA5 has no visibility); turbulence and icing from aviation products |
| TR-26-5 T7–T8 wet bands (wet, cold/wet) | The temperature part only | Precipitation and wetness | ERA5 total precipitation and precipitation type |
| TR-26-5 §1 wind rating for life-sustaining structures (100 mph) | Hourly-mean wind compared against 87 kn | Gusts (structures are rated for gusts) | Partly **already in AZCOT** (`var29` gusts at 06 and 18 UTC, a lower bound on the true peak); hourly ERA5 10 m gust (`10fg`) for the full record |
| ATP 3-90.96 T1-7 season chart | The temperature-zone column | Precipitation type, ground condition, river and lake ice condition | ERA5 precipitation type and lake-ice depth; break-up and freeze-up dates from observations |

## Not determined

| Table | What it decides | What's missing | Where it could come from |
|---|---|---|---|
| TR-26-5 §1 tentage (10 lb/ft²) and rigid shelters (20 lb/ft²) | Whether one 24-hour snowfall, or one multi-day storm, overloads a structure that is cleared afterwards | 24-hour and storm-total snowfall load | **Needs a new download:** ERA5 hourly snowfall (`sf`), summed over 24 hours or a storm. AZCOT only has SWE, the snow on the ground at each hour. Differencing it is unreliable, because data-assimilation jumps at fixed hours look like snowfall or cancel it, and melt is netted out. That only works as a rough cross-check. |
| TR-26-5 T9 gloves and mittens (arctic, OR mittens, trigger finger, convoy, contact) | Glove choice | Temperature ratings (manufacturers won't commit to one) | Manufacturer or test data |
| TR-26-5 T13 LCD screens | Display use | Temperature rating | Manufacturer specification |
| TR-26-5 T6 air trafficability, illumination | Low-level flight; night operations | Icing, visibility, precipitation; lunar illumination and elevation | Icing and visibility as above. Lunar values can be computed from astronomy, with no data needed. |
| ATP 3-90.96 T1-1, T1-2 snow wetness, density, hardness | Snow trafficability | Snow liquid-water content, density and hardness | ERA5 snow density. Our snow-load and snow-depth coverages come from two different models (ERA5 and ERA5-Land), so their ratio is not a reliable density. |
| ATP 3-90.96 T1-6 snowfall categories, blizzards | Visibility and accumulation categories | Snowfall rate, visibility, gusts | ERA5 snowfall; gusts partly from `var29` (06/18 UTC) or hourly ERA5 `10fg`; visibility only from external METAR/ASOS station archives |
| ATP 3-90.96 B-1 skis vs. snowshoes; B-4 over-snow movement rates | Foot and over-snow mobility | Vegetation (brush), terrain, snow type | Land-cover and elevation datasets, plus snow density |
| ATP 3-90.96 B-2 frost depth for crossing soft terrain | Whether the ground can bear a vehicle | Frost depth (AZCOT has only the 0–7 cm soil layer) and soil wetness | ERA5 soil temperature levels 2–4 (7–289 cm) |
| ATP 3-90.96 C-1 to C-5 ice load capacity | Vehicles, troops and landing zones on lake or river ice | Ice thickness | ERA5 lake-ice depth (lakes only), or an estimate from freezing degree-days of the air temperature we already have |
| MIL-HDBK-310 §5.1.14 ice accretion | Structural icing | Freezing rain and supercooled cloud | ERA5 precipitation type |
| MIL-HDBK-310 §5.1.12 · AR 70-38 T3-12 blowing snow | Abrasion and penetration | Blowing-snow mass flux | Could be modeled from wind plus snow cover |
| MIL-HDBK-310 §5.1.17–5.1.19 low pressure and density | Engine and aircraft performance | Surface pressure | ERA5 surface pressure |
| ATP 4-33 maintenance operations | — | — | No condition-to-equipment tables. Its cold-weather limits are the TM 4-33.31 values already in TR-26-5. |

## Caveats on the determined items

- **The equipment limits are single "minimum operational temperature" numbers** (mostly TM 4-33.31 via TR-26-5). They say nothing about duration, wind, or whether the item is pre-warmed or winterized, except where the table lists winterized variants separately. Some rows conflict:
  - Table 18 lists GO-75 twice (50 °F and −50 °F).
  - Table 12 lists rechargeable Type III/IV batteries as "Zone 1, −22 °F".
  - The thresholds are reproduced as published, and the conflicts are flagged in `thresholds.csv`.
- **Comparisons are against 2 m air temperature.** Equipment surfaces, cold-soaked metal and the snow surface can be colder (see AR 70-38's induced temperatures).
- **The data are a 0.25° (about 28 km) grid-cell climatology.** Valleys, ridges and microclimates at a real site can differ by tens of degrees, and inversion-prone interior valleys (e.g. Fairbanks) are typically colder than the cell average.
- **Wind is the hourly mean at 10 m, not gusts.** AZCOT's `var29` files hold instantaneous gusts, but only at 06 and 18 UTC, so they aren't used yet. Two samples a day would understate peak gusts.
- **1 °F / 1 kn / 1 in resolution.** Shares of hours come from 1-unit histograms. For limits that fall between bins (e.g. −52.6 °F) the bin containing the limit is counted as crossing, which is conservative.
