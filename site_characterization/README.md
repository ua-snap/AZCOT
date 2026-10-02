# Site characterization: proof of concept

**Pick a place → get a menu of what the manuals say works there, and what can't be decided yet.**

For a point, this proof of concept looks up the AZCOT cold-season climatology and checks it against every condition-to-equipment table in five source documents: ERDC/CRREL TR-26-5, ATP 3-90.96, MIL-HDBK-310, AR 70-38 and ATP 4-33. The output for each site is one page:

1. **At a glance:** climatic design type, cold zones, design-cold temperatures, frostbite danger, freeze–thaw, snow depth, snow load, wind.
2. **Shopping list:** about 100 items, grouped by category (worn gear, shelter, batteries, electronics, generators, fuels, oils, weapons, lubricants, aircraft, vehicles in snow), each rated **OK / Caution / No**, with the months that matter.
3. **Use-when guidance:** which clothing configuration and lubricants apply, and how often, by month.
4. **Operations stoplight:** the wind and temperature parts of the Combat Weather Team chart.
5. **Not determined:** what the manuals ask for that AZCOT doesn't have.

The eight example sites are the same as in the EDA and plots: [Fairbanks](sites/fairbanks_ak.md), [Utqiagvik](sites/utqiagvik_ak.md), [Yellowknife](sites/yellowknife_nt.md), [Eureka](sites/eureka_nu.md), [Pituffik](sites/pituffik_gl.md), [Tromsø](sites/tromso_no.md), [Norilsk](sites/norilsk_ru.md), [Oymyakon](sites/oymyakon_ru.md).

At a glance, out of the 106 evaluated items:

| Site | AR 70-38 design type | Design cold zone | Record low | OK | Caution | No |
|---|---|---|---:|---:|---:|---:|
| [Fairbanks, AK](sites/fairbanks_ak.md) | C2 Cold | 5A | -56 °F | 32 | 13 | 61 |
| [Utqiagvik, AK](sites/utqiagvik_ak.md) | C2 Cold | 4 | -56 °F | 32 | 34 | 40 |
| [Yellowknife, NT](sites/yellowknife_nt.md) | C2 Cold | 5A | -50 °F | 37 | 10 | 59 |
| [Eureka, NU](sites/eureka_nu.md) | C3 Severe cold | 5B | -61 °F | 28 | 7 | 71 |
| [Pituffik, GL](sites/pituffik_gl.md) | C2 Cold | 5A | -54 °F | 31 | 13 | 62 |
| [Tromsø, NO](sites/tromso_no.md) | C1 Basic cold | 3 | -24 °F | 75 | 7 | 24 |
| [Norilsk, RU](sites/norilsk_ru.md) | C2 Cold | 5A | -57 °F | 31 | 13 | 62 |
| [Oymyakon, RU](sites/oymyakon_ru.md) | C4 Extreme cold | 5C | -79 °F | 8 | 4 | 94 |

Every site page explains the verdicts with the months involved. The large "No" counts are expected: much standard-issue gear is rated well above what interior Arctic winters reach. The pages show which winterized or arctic alternatives are OK.

**[data_gaps.md](data_gaps.md)** covers the other half of the question: which tables can't be applied yet, and what data each one needs.

## How a verdict is made

Each item in [thresholds.csv](thresholds.csv) has a limit, for example a minimum operating temperature of −53 °F for JP-8. For each month, the item's limit is compared with that site's 30-year climatology (1991–2020, October–March):

| Verdict | Meaning |
|---|---|
| **OK** | The 30-year record never crosses the limit, e.g. the record low stays above it. |
| **Caution** | The limit is crossed, but in no more than 1% of a month's hours. This is the MIL-HDBK-310 / AR 70-38 design convention, under which equipment is designed for all but the coldest 1% of hours in the worst month. The months are named. |
| **No** | More than 1% of a month's hours cross the limit. The months are named. |

The comparisons use:
- **Equipment, clothing and fluids:** 2 m air temperature.
- **Vehicles:** snow depth.
- **Shelters:** snow load and wind.
- **Frostbite:** wind chill, approximated as in [plots.md](../plots/plots.md#3-frostbite-danger-levels).

The shares of hours come from the monthly hourly-value histograms in the preprocessed coverages, so any limit can be evaluated exactly to the nearest degree.

Each site uses its nearest seasonal-land grid cell, 0.25° (about 28 km). A real site in a valley or on a ridge can be much colder or warmer than its grid cell, especially in inversion-prone interior valleys.

## Running it

```bash
PY=~/micromamba/envs/azcot-eda/bin/python
$PY site_characterization/scripts/characterize.py                 # all 8 sites -> sites/*.md, sites/summary.csv
$PY site_characterization/scripts/characterize.py fairbanks_ak    # one site
```

To add a site, append `(name, lat, lon)` to `SITES` in `scripts/characterize.py`. To add or correct a manual entry, edit `thresholds.csv`; each row names its source document and table. The script reads only the coverages in `/beegfs/CMIP6/jdpaul3/azcot_preprocess/coverages/` (see [preprocess/README.md](../preprocess/README.md)).

## Toward an app

The pieces an app would need already exist:
- **A rules catalog** (`thresholds.csv`) separate from the code.
- **Gridded coverages** that answer "share of hours beyond any limit" for any cell.
- **A per-point evaluator** (`characterize.py`).

A web version would swap the fixed site list for a clicked coordinate, and render the same sections from the evaluator's output instead of Markdown. The main work left is in [data_gaps.md](data_gaps.md): gusts, ceiling, visibility, precipitation, ice and frost depth.

## Source documents

Text extracted to `reference/` for searching:

| Document | Contents |
|---|---|
| ERDC/CRREL TR-26-5 (2026) | Tables 1–30 |
| ATP 3-90.96 / MCTP 12-10E (2025) | Arctic Operations |
| MIL-HDBK-310 (1997) | Global Climatic Data for Developing Military Products |
| AR 70-38 (2020) | Research, Development, Test and Evaluation of Materiel for Worldwide Use |
| ATP 4-33 (2019) | Maintenance Operations; it has no condition-based tables |
