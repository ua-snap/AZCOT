# Mock AZCOT point-query response

[`fairbanks_ak.json`](fairbanks_ak.json) is a mock of what an AZCOT point-query API could return for one location (Fairbanks, AK: 64.84 °N, 147.72 °W). Use it to start testing the application and the report section before the real API endpoint exists.

- **The values are real.** They are read from the AZCOT climatology coverages (ERA5, cold season October–March, 1991–2020) at the grid cell an API would pick for this location.
- **The structure is a proposal.** The endpoint (`/azcot/point/<lat>/<lon>`), field names and nesting are open to change. It follows the style of some of SNAP's existing Data API returns: a `metadata` block, then sections nested as *variable → statistic → period*.
- **What's in it:** climate statistics, design cold and cold zones, exceedance frequencies, frostbite danger levels, snowfall design loads, and OK / Caution / No verdicts for the climate-based design limits.
- **What's not in it:** equipment, clothing, fuel and similar verdicts (the "shopping list" on the site pages: out of scope for this app right now).

## Layout

```
metadata                  query point, grid cell used, period, units, caveats, and every coverage read (coverages_used)
climatology               air_temperature, wind_chill, wind_speed, snow_depth, snow_load   -> min / mean / max
                          freeze_thaw_days                                                 -> value
design_and_zones          coldest month, design cold (1/5/10%), record low, AR 70-38 design type, ATP cold zones
exceedance                % of hours beyond thresholds, per variable -> thresholds -> "<value>" -> periods
frostbite                 share of hours per danger level (red / amber / green / none) + shortest time to frostbite
snowfall_loads            variables -> 24-hour, 72-hour and storm-total snowfall loads (records, means, % of years)
climate_limit_verdicts    legend + items[]: OK / CAUTION / NO per design limit, overall and by month, with evidence
```

### Periods

Most values come in three resolutions, under these keys:

| Key | Contents |
|---|---|
| `daily` | object keyed `oct_01` … `mar_31` (182 days; there is no Feb 29). Each calendar day pools 30 years × 24 hours. |
| `monthly` | object keyed `oct`, `nov`, `dec`, `jan`, `feb`, `mar` |
| `seasonal` | a single number for the whole October–March season |

Some quantities exist only monthly and seasonally, because no daily coverage exists: exceedance shares from the hourly histograms, freeze–thaw days, design cold, and the per-year counts in `snowfall_loads`. A value of `null` means the quantity is undefined there. For example, `frostbite.shortest_time_to_frostbite` is `null` in a period where the air never got cold enough for frostbite.

Example (air temperature, record lows):

```json
"climatology": {
  "air_temperature": {
    "units": "degF",
    "source": {"min": {"daily":   {"coverage_id": "azcot_t2_climatology_daily",   "band": "t2_min", "axis": "mmdd"},
                       "monthly": {"coverage_id": "azcot_t2_climatology_monthly", "band": "t2_min", "axis": "month"}, …}},
    "min": {"daily": {"oct_01": 20.76, …, "jan_15": -47.77, …}, "monthly": {"oct": -29.06, …}, "seasonal": -55.52},
    …
```

### Units

US customary throughout: °F, knots (10 m hourly mean wind), inches (snow depth), lbf/ft² (loads). Shares are in %. Each block states its own `units`.

### Where each number comes from

Every block has a `source` naming the **Rasdaman coverage id** and **band** it was read from, plus the axis it varies along. These are the coverage ids of the draft ingest recipes ([rasdaman/](../rasdaman/README.md)). `metadata.coverages_used` lists each coverage once, with the grid cell read and an example WCPS query that would fetch the same values once the coverages are ingested. The coverages are not in Rasdaman yet, so the values were read from the ingest-ready NetCDF files.

### Verdicts

`climate_limit_verdicts.items` has one entry per design limit, all from [site_characterization/thresholds.csv](../site_characterization/thresholds.csv):
- **vehicle type vs. snow depth** (`T3a`–`T3e`);
- **structure snow loads**: tentage 10 lbf/ft² from one 24-hour snowfall (`SLa`), rigid shelters 20 lbf/ft² from one storm (`SLb`), life-sustaining structures 25 lbf/ft² (`SLc`), semipermanent structures 48 lbf/ft² (`SLd`);
- **the 100 mph structure wind rating** (`WNa`).

Each entry has an overall `verdict`, a `by_month` verdict, and the `evidence`: the monthly 30-year record and the share of hours (or of years) over the limit. `legend` defines the classes:
- **OK:** the 30-year record never reaches the limit.
- **CAUTION:** the limit is reached rarely: in at most 1% of the month's hours, or at most 10% of years for the snowfall loads.
- **NO:** more often than that.
- **N/A:** not meaningful at that cell.

These match the Fairbanks [site page](../site_characterization/sites/fairbanks_ak.md).

## Caveats to carry into the app or report

- **Grid cell, not site.** Values describe a 0.25° ERA5 cell (about 28 km; here 10 km from the site) or, for snow depth, a 0.1° ERA5-Land cell. Valleys and ridges can be much colder or warmer, especially under winter inversions.
- **Wind chill is AZCOT's.** It is computed from *skin* temperature rather than the 2 m air temperature its report states, which runs a few °F colder over land. The frostbite levels use air temperature.
- **Storm totals depend on our storm definition** (dry gaps of at most 12 h), because the report gives none. See [preprocess/storm_definition/](../preprocess/storm_definition/README.md).
- **Wind is the hourly mean;** there are no gusts.
- **Snow depth** is missing 23 hours on the last day of every month in the source data, so those days rest on fewer values.

## Regenerating, or another point

```bash
PY=~/micromamba/envs/azcot-preprocess/bin/python
$PY mock_api/make_point_json.py                                         # Fairbanks -> mock_api/fairbanks_ak.json
$PY mock_api/make_point_json.py --name "Utqiagvik, AK" --lat 71.29 --lon -156.79   # -> mock_api/utqiagvik_ak.json
```

It reads the Rasdaman-ready coverages in `/beegfs/CMIP6/jdpaul3/azcot_preprocess/rasdaman/` (built by `rasdaman/prep_coverages.py`), and the same functions the site pages use for cell selection, cold zones, design type and verdicts.
