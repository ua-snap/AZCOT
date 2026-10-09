# Tromsø, NO: site characterization

*Proof of concept. AZCOT ERA5 climatology 1991–2020, October–March. Grid cell 69.75°N 19.00°E (11 km from the site, surface type: land); snow depth from the ERA5-Land cell 69.70°N 19.00°E. See [README](../README.md) for how verdicts are made and [data_gaps.md](../data_gaps.md) for what can't be determined.*

## At a glance

| | |
|---|---|
| Coldest month | Jan (mean air temperature 19 °F) |
| Design cold, coldest month (1% / 5% / 10% of hours colder) | -12 / -4 / 2 °F (MIL-HDBK-310 convention) |
| Record low air temperature (30 winters) | -24 °F (Jan) |
| AR 70-38 climatic design type | **C1 Basic cold** (from the coldest-month 1% value) |
| ATP 3-90.96 cold zone: typical / design / record | 2 / 3 / 4 |
| Safety tables that apply (ATP 3-90.96 App. F) | F-1 / F-6, F-2 / F-7, F-3 / F-8 |
| Frostbite danger (TR-26-5 Eq. 5), share of Oct–Mar hours | green 9% · amber 9% · red 0.0% (red never reached) |
| Freeze-thaw days per winter | 55 (Oct 10, Nov 10, Dec 10, Jan 7, Feb 7, Mar 10) |
| Snow depth: typical peak / record | 54 / 88 in |
| Snow load: typical peak / record | 30 / 86 lb/ft² |
| Snowfall load: record 24-hour / 72-hour / storm total | 7.3 / 12.9 / 30.9 lb/ft² (tentage limit 10, rigid shelters 20; storm = snowfall with lulls of at most 12 h, a definition we chose: see [storm definition](../../preprocess/storm_definition/README.md)) |
| Wind (10 m hourly mean): record | 27 kn (hourly mean; gusts not used, see data gaps) |

## Shopping list

**OK** = the 30-year record low (or high) never crosses the item's limit. **Caution** = only rare hours (≤ 1% of a month) cross it, in the months named. **No** = more than 1% of hours cross it, in the months named. Limits are shown in parentheses.

**Vehicles in snow**

- OK: Over-snow vehicle (no limit)
- No: Wheeled vehicle (8 in; no in Oct–Mar); Wheeled 4x4 or greater (15 in; no in Oct–Mar); Wheeled 4x4 or greater with snow chains (20 in; no in Nov–Mar, caution in Oct); Tracked vehicle (40 in; no in Dec–Mar, caution in Nov)

**Worn gear**

- OK: Vapor barrier boots (-50 °F); Mukluk boots (-40 °F); Complete sleep system wearing ECWCS (-50 °F)
- Caution: Danner boots (400 g, 600 g, 1200 g) (-20 °F; in Dec–Feb)
- No: Standard issue light duty leather gloves (35 °F; no in Oct–Mar); Type I temperate sleeping bag inner (15 °F; no in Oct–Mar); Type II cold sleeping bag (stand alone) (5 °F; no in Nov–Mar, caution in Oct); Type III (Type II over Type I) (-13 °F; no in Dec, Feb, caution in Jan, Mar); Modular sleeping bag intermediate cold (0 °F; no in Nov–Mar, caution in Oct)

**Equipment**

- OK: Electrical and ignition systems (-30 °F); Vehicle crew heaters (-25 °F); Personnel heaters (-40 °F); Level vials (-40 °F); Cold-soaked vehicles (start without pre-warming) (-25 °F)

**Shelter**

- OK: Arctic 10-man tent (Ahkio) (-40 °F); HDT Airbeam (-25 °F); HDT Airbeam (Arctic) (-65 °F); Base-X (-40 °F); Deployable Rapid Assembly Shelter (DRASH) (-40 °F); Portable equipment / tentage (10 lb/ft2 from a 24-hour snowfall) (10 lb/ft² from one 24-hour snowfall); Life-sustaining structures (100 mph wind) (87 kn (hourly mean))
- Caution: Temporary rigid shelters / portable hangars (20 lb/ft2 from a multi-day storm) (20 lb/ft² from one storm total; in Dec, Feb–Mar)
- No: Life-sustaining structures (25 lb/ft2) (25 lb/ft²; no in Jan–Mar, caution in Dec); Semipermanent (demountable) structures (48 lb/ft2 seasonal accumulation) (48 lb/ft²; no in Jan–Mar)

**Batteries**

- OK: AGM battery (fully charged) (-70 °F); Fully charged battery (general) (-70 °F); Gel battery (fully charged) (-70 °F); Lithium battery Li-SO2 (-58 °F); Wet cell battery (fully charged) (-75 °F)
- Caution: Lithium battery LiMnO2 (-22 °F; in Jan–Feb); Rechargeable dry cell Type III and IV (-22 °F; in Jan–Feb)
- No: Battery storage (10 °F; no in Oct–Mar); AGM battery (not fully charged) (10 °F; no in Oct–Mar); Rechargeable dry cell Type I and II (-4 °F; no in Dec–Mar, caution in Oct–Nov)

**Electronics**

- OK: Handheld computers (-30 °F); Digital light processing projectors (-40 °F); Mortar ballistic computer (-50 °F); RG213 coaxial cable (-40 °F)
- Caution: RG-8 cable (-20 °F; in Dec–Feb)
- No: Larger workstation computers (0 °F; no in Nov–Mar, caution in Oct); Ruggedized display / projection (-4 °F; no in Dec–Mar, caution in Oct–Nov)

**Generators**

- OK: MEP (nonwinterized) (-25 °F); MEP (winterized) (-50 °F); Generator storage (-60 °F); Military Tactical Generator (MTG) (-50 °F); TQG (nonwinterized) (-25 °F); TQG (winterized) (-50 °F); AMMPS (-50 °F); Power distribution and illumination system (-25 °F)

**Fuels**

- OK: JP-8 (-53 °F); F-24 (-40 °F); Jet A (-40 °F); Jet A-1 (-52.6 °F); Jet B (-58 °F); JP-5 (-51 °F); JP-4 (-74 °F); Antarctic jet fuel (AN-8) (-74 °F)

**Engine oils**

- OK: OE/HDO-SCPL (-58 °F); OEA-30 (-58 °F); OE/HDO-5/40 (-30 °F)
- Caution: OE/HDO-10/30 (-15 °F; in Dec–Mar)
- No: OE/HDO 40 (20 °F; no in Oct–Mar); OE/HDO-15/40 (0 °F; no in Nov–Mar, caution in Oct); 15W40 (transmission oil) (-10 °F; no in Dec–Feb, caution in Oct–Nov, Mar)

**Hydraulic fluids**

- OK: MIL-PRF-6083 / OHT (-65 °F); MIL-PRF-46170 / FRH (-40 °F); MIL-PRF-5606 / OHA (-65 °F); MIL-PRF-83282 (-40 °F); MIL-PRF-87257 (-65 °F); MIL-PRF-46176 (-67 °F)

**Gear oils**

- OK: GO-75 (second entry) (-50 °F)
- Caution: GO-80/90 (-18 °F; in Dec–Feb)
- No: GO-75 (first entry) (50 °F; no in Oct–Mar); GO-85/140 (4 °F; no in Nov–Mar, caution in Oct)

**Greases**

- OK: Grease (automotive and artillery) (-65 °F); Grease (aircraft general purpose wide temperature range) (-65 °F); Grease (aircraft and instrument; gear and actuator screw) (-99 °F); Grease (molybdenum disulfide; low and high temperature) (-100 °F)
- No: Grease (graphite) (-9 °F; no in Dec–Feb, caution in Oct–Nov, Mar)

**Solvents and liquids**

- OK: Propylene-glycol deicing fluid (-60 °F); Propane (-40 °F); Arctic antifreeze (-90 °F); Wheel bearing lubricants (-65 °F); Lubricating oil, internal combustion engine, arctic (-67 °F); Ethylene-glycol / distilled water mixture (-50 °F); Arctic antifreeze (ethylene-glycol based) (-40 °F)
- No: Rifle bore cleaner (RBC) (32 °F; no in Oct–Mar)

**Weapons**

- OK: Machine guns (-40 °F); Rifles (-40 °F); Rockets (-40 °F)

**Weapon lubricants**

- OK: PL-S (-49 °F); Cleaner lubricant preservative (CLP) (-60 °F); Lubricant small arms (LSA) (-65 °F); LSAT (semifluid high-load) (-30 °F); Lubricant arctic weight (LAW) (-70 °F)

**Lubrication schedule**

- OK: M249 SAW: CLP (effective to -30 F) (-30 °F)
- Caution: Machine guns: LSAT / GMD / LAW (to -20 F) (-20 °F; in Dec–Feb)
- No: Artillery: CLP (to -10 F) (-10 °F; no in Dec–Feb, caution in Oct–Nov, Mar)

**Aircraft**

- OK: CH-47 Chinook (-40 °F); AH-64 Apache (-40 °F); UH-60 Blackhawk (-40 °F); LC-130 (-65 °F); C-17 (-76 °F)

## Use-when guidance (share of hours in each band, by month)

| Guidance | Oct | Nov | Dec | Jan | Feb | Mar |
|---|---:|---:|---:|---:|---:|---:|
| Cold 0 to 30 F: levels 1+2+5 | 20% | 50% | 59% | 68% | 67% | 64% |
| Extreme cold -25 to 0 F: levels 1+2+3+5 | · | 1% | 7% | 9% | 9% | 2% |
| Below -25 F: no active-wear configuration published | · | · | · | · | · | · |
| Cold 0 to 30 F: levels 2+5+7(T) | 20% | 50% | 59% | 68% | 67% | 64% |
| Extra cold -50 to 0 F: levels 1+2+3+5+7 | · | 1% | 7% | 9% | 9% | 2% |
| Below -50 F: no static-wear configuration published | · | · | · | · | · | · |
| Rifles: CLP or LSA (above -10 F) | 100% | 100% | 98% | 98% | 98% | 100% |
| Rifles: LAW (10 F and below) | 1% | 7% | 17% | 24% | 22% | 8% |
| Mortars: general purpose lubricant (above 10 F) | 99% | 93% | 83% | 76% | 78% | 92% |
| Mortars: LAW (below 10 F) | 1% | 7% | 17% | 24% | 22% | 8% |
| Mortars: PL special purpose (below 0 F) | · | 1% | 7% | 9% | 9% | 2% |

## Operations stoplight (wind or temperature only; share of Oct–Mar hours)

Partial: TR-26-5 Table 6 also needs ceiling, visibility, precipitation, turbulence, icing and gusts (see [data_gaps.md](../data_gaps.md)).

| Operation | Favorable | Marginal | Unfavorable | Worst month (unfavorable) |
|---|---:|---:|---:|---|
| Airborne ops (static line) | 97% | 1% | 2.2% | Dec 3.2% |
| Fixed wing | 100% | 0% | 0.0% | never |
| Rotary wing | 100% | 0% | 0.0% | never |
| Medevac ops | 100% | — | 0.0% | never |
| Gray Eagle UAV (wind) | 100% | 0% | 0.0% | Feb 0.0% |
| Gray Eagle UAV (temperature) | 100% | 0% | 0.0% | Jan 0.0% |
| Shadow UAV (wind) | 99% | 1% | 0.0% | Feb 0.0% |
| Personnel (temperature) | 71% | 29% | 0.3% | Feb 0.7% |
| Air assault | 100% | 0% | 0.0% | never |
| CH-47 sling load | 99% | 1% | 0.0% | never |
| CH-60 sling load | 91% | 8% | 0.9% | Jan 1.3% |
| FARP ops | 100% | 0% | 0.0% | never |

## Not determined from AZCOT data

- Air trafficability (< 1000 ft) (TR-26-5 Table 6): needs Precipitation, icing, visibility
- Illumination (TR-26-5 Table 6): needs Lunar illumination and elevation (computable from astronomy, not in AZCOT)
- Wet ~40 F: levels 1+4+5(B) (TR-26-5 Table 7): needs Precipitation / wetness (temperature alone cannot identify wet conditions)
- Cold/wet 35 to 45 F: levels 1+5 (TR-26-5 Table 7): needs Precipitation / wetness
- Cold/wet 30 to 45 F; wet above 45 F (TR-26-5 Table 8): needs Precipitation / wetness
- Arctic mittens; OR mittens; OR trigger finger mittens; OR convoy gloves; OR contact gloves (TR-26-5 Table 9): needs Manufacturer temperature ratings
- LCD screens (TR-26-5 Table 13): needs Manufacturer temperature ratings
- Season chart (winter / break-up / summer / freeze-up) (ATP 3-90.96 Table 1-7): needs Precipitation type, ground condition, river and lake ice condition
- Snow wetness and density / hardness (trafficability) (ATP 3-90.96 Tables 1-1 and 1-2): needs Snow liquid-water content and density/hardness (SWE/depth ratio could estimate density, but SWE is ERA5 and depth is ERA5-Land)
- Snowfall categories and blizzards (ATP 3-90.96 Table 1-6): needs Snowfall rate, visibility, gusts
- Skis vs snowshoes (ATP 3-90.96 Table B-1): needs Vegetation and terrain
- Frost depth for crossing soft terrain (ATP 3-90.96 Table B-2): needs Frost depth / soil temperature profile (AZCOT has only the 0-7 cm soil layer STL1) and soil wetness
- Over-snow movement planning rates (ATP 3-90.96 Table B-4): needs Snow type, terrain and vegetation
- Ice load capacity / landing zones on freshwater ice (ATP 3-90.96 Tables C-1 to C-5): needs Lake and river ice thickness (could be estimated from freezing degree-days of the air temperature)
- Ice accretion on structures (MIL-HDBK-310 5.1.14): needs Freezing rain / supercooled cloud frequency
- Blowing snow mass flux (MIL-HDBK-310 / AR 70-38 5.1.12 / Table 3-12): needs Blowing-snow flux (could be modeled from wind speed plus snow cover)
- Low pressure / air density (MIL-HDBK-310 5.1.17-5.1.19): needs Surface pressure (not in AZCOT)
