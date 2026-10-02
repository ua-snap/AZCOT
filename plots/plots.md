# AZCOT plots from the preprocessed coverages

This document redraws the EDA's operational maps and charts ([eda/EDA.md](../eda/EDA.md) §4) from the curated NetCDF coverages built by [preprocess/](../preprocess/README.md). It also adds two things:

- **How to draw glaciers on snow-load maps** using the `surface_type` flag (§2).
- **Frostbite danger-level maps** in the green / amber / red classes of ERDC/CRREL TR-26-5 Tables 4–5 (§3).

All figures come from the coverages in `/beegfs/CMIP6/jdpaul3/azcot_preprocess/coverages/`. Nothing reads the raw AZCOT data. To regenerate them, see §4.

**What changed from the EDA versions:**
- **Wind chill lows are true record lows.** `wct_min` replaces the EDA's `min_WCT`, which was an average of yearly lows. On the point charts the dotted line now sits *below* the percentile band, where a record low belongs.
- **Feb 29 is gone**, along with the Mar 1 spikes it caused.
- **Glaciers and perennial snow are drawn from `surface_type`** (gray tones), not from the EDA's ad-hoc mask.
- **Point charts use the nearest seasonal-land cell** (`surface_type == 1`). The eight locations land on the same grid cells as in the EDA, and the values agree (`tables/locations.csv`).

---

## 1. EDA §4 questions, redrawn

### Q1. How cold does it typically feel, where, and in which month?

![Average wind chill by month](figures/q1_wct_monthly_mean.png)

From `azcot_wct_climatology_monthly.nc` `wct_mean`. Greenland is coldest in every month. By December–February the Canadian Arctic Archipelago and interior northeastern Siberia approach it, while the North Atlantic side stays mild.

### Q2. How often is wind chill dangerous (≤ −40 °F)?

![Share of hours at or below −40 °F](figures/q2_wct_freq_le_m40_monthly.png)

From `azcot_wct_stats_monthly.nc`, `wct_frequency.sel(wct_threshold=-40)`. Any threshold from 0 to −100 °F in 5 °F steps works the same way.

### Q3. Where does the Army's −65 °F requirement actually matter?

![Share of hours at or below −65 °F](figures/q3_wct_freq_le_m65_season.png)

Seasonal and worst-month shares of hours at or below −65 °F. These are concentrated on the Greenland ice sheet, the Canadian Archipelago, and northeastern Siberia.

### Q4. Which cold zone should a unit equip for?

![ATP cold zones from wind chill](figures/q4_wct_cold_zones.png)

ATP 3-90.96 cold zones applied to the typical January hour (`wct_mean`) and to the January 1st-percentile hour (the daily `wct_percentile` averaged over January). Shown on land only (`surface_type > 0`).

### Q5. How does a specific site behave through the season?

![Wind chill at eight locations](figures/q5_wct_points_seasonal.png)

The band runs from the 1st to the 50th percentile hour. The dotted line is now the **true record low** for each calendar day; Fairbanks, for example, reaches −72.9 °F. In the EDA this line was `min_WCT`, which sat inside or even above the band.

### Q6. How long do dangerous spells last?

![Frequency vs. persistence](figures/q6_wct_jan_freq_vs_duration.png)

The same caveat as in the EDA applies. `wct_consecutive` counts years with no spell as 0, so it mixes how often spells happen with how long they last, and it tracks the frequency map closely.

### Q7. How heavy is the snow load, and how does it build?

![Average snow load by month](figures/q7_sl_monthly_mean.png)

From `azcot_sl_climatology_monthly.nc` `sl_mean`. Glacier and perennial-snow cells are drawn in gray from `surface_type` (see §2).

### Q8. Which structure design loads hold up?

![Typical vs record snow load](figures/q8_sl_design_classes.png)

Left: the typical seasonal peak (highest 30-year-average day, from the daily `sl_mean`). Right: the 30-year record (`sl_max`, seasonal). The design loads are from TR-26-5 §1.

### Q9. When in the season does snow load arrive?

![First exceedance of 10 and 25 lb/ft²](figures/q9_sl_first_exceedance.png)

The first day on which the daily `sl_mean` crosses each threshold (the SR-25-2 §3.6 method).

### Q10. Snow load through the season at specific sites

![Snow load at eight locations](figures/q10_sl_points_seasonal.png)

### Location summary (`tables/locations.csv`)

| Location | Jan avg WCT (°F) | Jan 1st-pct WCT (°F) | Record low WCT (°F) | % hrs ≤ −40 | % hrs ≤ −65 | % hrs green | % hrs amber | % hrs red | Peak avg SL | Record SL | Avg SL ≥ 25 from |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Fairbanks, AK | −15.8 | −60.0 | −72.9 | 4.6 | 0.09 | 30.8 | 19.7 | 0.39 | 17.3 | 77.3 | never |
| Utqiagvik, AK | −33.9 | −65.8 | −88.2 | 19.8 | 0.82 | 24.1 | 52.4 | 2.06 | 16.3 | 26.5 | never |
| Yellowknife, NT | −30.3 | −66.2 | −74.9 | 12.7 | 0.39 | 26.2 | 38.0 | 1.03 | 13.3 | 22.7 | never |
| Eureka, NU | −55.0 | −78.0 | −93.7 | 60.2 | 10.59 | 10.7 | 68.1 | 18.96 | 4.6 | 10.2 | never |
| Pituffik, GL | −43.2 | −71.7 | −90.7 | 36.4 | 3.24 | 20.5 | 64.4 | 6.68 | 25.3 | 49.6 | Mar 28 |
| Tromsø, NO | 2.5 | −30.7 | −47.8 | 0.1 | 0.00 | 19.3 | 4.4 | 0.00 | 35.7 | 86.3 | Feb 22 |
| Norilsk, RU | −39.5 | −78.0 | −96.1 | 27.9 | 3.89 | 24.2 | 52.8 | 6.70 | 34.1 | 66.0 | Feb 4 |
| Oymyakon, RU | −52.9 | −80.3 | −94.2 | 46.9 | 8.25 | 15.2 | 59.5 | 14.07 | 9.6 | 17.3 | never |

The percentages are shares of all Oct–Mar hours. Green, amber and red are the frostbite danger levels from §3.

---

## 2. Drawing glaciers and perennial snow on snow-load maps

The snow-load coverages are **NaN** wherever `surface_type ≠ 1`, which covers ocean, glacier, and perennial snow. The reason is that ERA5 does not model snow on glaciers. It holds them at a constant 10 m of water equivalent, which equals 2047 lb/ft² (Muñoz-Sabater et al. 2021; see the [preprocess README](../preprocess/README.md#glaciers-and-surface_type)). The figure below shows the same quantity, the highest hourly snow load in 30 winters, drawn four ways.

![Four ways to draw the glacier cells](figures/sl_surface_types_4ways.png)

- **A. Raw values, scale to the data maximum.** The 2047 cap sets the top of the color scale, so every real snow load on Earth (0–90 lb/ft²) lands in the lightest color. The map says nothing.
- **B. Raw values, useful scale.** The real loads become visible, but Greenland, Svalbard, and the ice caps now look like the heaviest snow loads anywhere. A planner would wrongly conclude those are the worst places for structures.
- **C. The coverage as stored (NaN).** The misleading values are gone, but glaciers now look exactly like ocean or missing data. A reader can't tell "no snow-load estimate here because it's an ice sheet" from "no data" or "sea".
- **D. Coverage plus `surface_type`.** Real loads use the normal color scale, and glaciers (light gray) and perennial snow (dark gray) get their own legend entries. This is the recommended map product.

![Close-up of the perennial-snow ring](figures/sl_surface_types_zoom.png)

The close-up shows why there are *two* classes. ERA5 applies the 10 m constant only to grid boxes that are more than 50% ice. The partly glaciated boxes around them use the normal snow model, but their snow never melts out in summer, so it piles up year after year to 500–2000 lb/ft². On Svalbard and Iceland these perennial-snow cells (dark gray) outnumber the capped glacier cells (light gray). Masking only the capped cells would leave a ring of absurd snow loads around every ice cap.

**When to symbolize `surface_type`:**

- **Any map a person will read**, such as planning maps, Atlas-style products, or briefings. It turns "missing" into an explanation and stops readers inferring "no snow", "no data" or "worst snow load".
- **When glaciers are part of the area of interest**, e.g. Greenland, Svalbard, the Canadian Archipelago, coastal Alaska ranges, or Iceland. Operations there still need to know the surface is ice, even though there's no meaningful snow-load number.
- **In legends and statistics tables**, to report how much of a region is glacier or perennial snow instead of silently dropping it.

**When it isn't needed:**

- **Numeric analysis of seasonal snow load**, such as area averages, thresholds, or the design-load percentages in Q8. The NaN mask already excludes the right cells. Use `surface_type` only to report what was excluded.
- **Wind chill maps.** WCT isn't masked: wind chill over ice and sea ice is physically meaningful. Use `surface_type > 0` only if you want land-only WCT maps (as in Q4).

**How to do it** (for any tool that layers rasters): draw the snow-load variable first, then add `surface_type` as a second layer showing only classes 2 and 3 in their own colors. In Python this is `draw_surface_types()` in `plots/scripts/style.py`. In ArcGIS or QGIS, add `surface_type` with a unique-values renderer and make classes 0 and 1 transparent.

---

## 3. Frostbite danger levels

TR-26-5 (Tables 4 and 5, from Nelson et al. 2002) defines three frostbite danger levels by **time until frostbite on dry, exposed skin**:

| Level | TR-26-5 color | Time to frostbite |
|---|---|---|
| Slight danger | green | < 120 min |
| Increased danger | orange (shown here as **amber**) | < 45 min |
| Great danger | red | ≤ 5 min |

### Why not read the classes straight off Table 4?

Table 4 lists wind chill values, so it looks as if it could be applied to wind chill directly. But its cells are colored by **time to frostbite**, which depends on air temperature and wind speed *separately*, not on wind chill alone. As a result, the same wind chill gets different colors in different cells. For example, −17 °F is green at 50 mph but orange at 25 mph, and −64 °F is still orange at 15 mph while −60 °F is already red at 30 mph. The coverages hold only wind chill, so any map built from them needs one cut-off per class. The figure compares the published table (left) with the cut-offs used here (right):

![Table 4 vs wind-chill-only classes](figures/fb_table4_check.png)

| Level | Wind chill cut-off used here | Basis |
|---|---|---|
| Slight (green) | −20 < WCT ≤ 0 °F | The table's own "< 120 min" definition. The report's frostbite-time equation (Eq. 5) puts 120 minutes at WCT ≈ 0 °F (−5 to +6 °F across 5–50 mph). |
| Increased (amber) | −60 < WCT ≤ −20 °F | Best fit to the table's orange/red coloring. |
| Great (red) | WCT ≤ −60 °F | Best fit to the table's coloring; Eq. 5 puts 5 minutes at WCT ≈ −60 °F. |

Of Table 4's 180 cells, 36 get a different class:
- **23** are cells the table shades green at wind chills of +1 to +19 °F (air temperatures of 10–25 °F). By Eq. 5, frostbite takes more than 120 minutes there, so the shading contradicts the table's own "< 120 min" label. (Table 5 also shades ">120 min" cells green, which points to an inconsistency in the report rather than in this method.) These cells also can't be reproduced from the coverages, whose wind chill frequencies stop at 0 °F.
- **10** lie on the amber/red edge, which depends on wind. At high wind, red starts near −51 °F; at low wind, amber lasts to −72 °F.
- **3** lie on the green/amber edge (−17 to −19 °F).

Two smaller issues in the report itself:
- Table 4's 15 °F column duplicates the 10 °F column (e.g. 6, 6 at 15 mph).
- Eq. 5 doesn't reproduce Table 5's minutes exactly; at −10 °F and 5 mph it gives 14 minutes against the table's 31.

**Treat these maps as a wind-chill approximation of the TR-26-5 classes.** An exact version would classify every hour from air temperature and wind speed. That needs one extra preprocessing step reading the raw hourly 2T and wind files, about 15 minutes on SLURM.

### What share of hours falls in each danger level?

Each share comes straight from the coverage frequencies:
- red = `wct_frequency(−60)`
- amber = `wct_frequency(−20)` − `wct_frequency(−60)`
- green = `wct_frequency(0)` − `wct_frequency(−20)`

![Seasonal share of hours per danger level](figures/fb_seasonal_shares.png)

Averaged over all land cells (including the ice sheets, as unweighted pixel means), Oct–Mar hours divide roughly as follows:

| Level | Share of Oct–Mar hours |
|---|---:|
| No frostbite danger | 25% |
| Green | 20% |
| Amber | 45% |
| Red | 11% |

In January the red share rises to 19%. Red occurs at some point on **92% of land**, and in at least 10% of hours in its worst month on **57%**. The land that never reaches red is mostly Scandinavia (about 3,900 of the ~5,700 cells), followed by Iceland, coastal south Greenland, and southern Alaska.

**By month, one map series per level:**

![Green: slight danger](figures/fb_green_monthly.png)

![Amber: increased danger](figures/fb_amber_monthly.png)

![Red: great danger](figures/fb_red_monthly.png)

Red, where frostbite takes 5 minutes or less, is a Greenland-only signal in October. It spreads across the Canadian Archipelago and Siberia from November, peaks in January–February (above 50% of hours on the Greenland ice sheet), and pulls back in March.

### Which level dominates each month?

![Most common danger level by month](figures/fb_dominant_monthly.png)

For a single map per month, this shows the class (including "no danger") that covers the most hours in each grid cell. Amber dominates most of the Arctic from November to March. Red dominates the Greenland interior and, in midwinter, the northern Canadian Archipelago. Because each cell shows only one class, this map hides how much of the time the other classes occur, so use the per-level maps above for planning.

---

## 4. Reproducing

```bash
PY=~/micromamba/envs/azcot-eda/bin/python     # spec: eda/environment.yml
cd plots/scripts
$PY make_plots.py              # all figures + tables/locations.csv (a few minutes on a login node)
$PY make_plots.py q8 fb_red    # or just some: q1..q10, surface, surface_zoom, fb_monthly, fb_seasonal,
                               #   fb_dominant, fb_table4, tables
```

Set `AZCOT_PRE_OUT` to read coverages from a different preprocess output root. The code is in `scripts/style.py` (palette, polar maps, `surface_type` symbology) and `scripts/make_plots.py` (one function per figure; the frostbite cut-offs are set once in `FB_CUTS` and applied by `fb_shares()`).
