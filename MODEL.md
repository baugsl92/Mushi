# Mushroom Watch 2.0 model specification

## Intended use

The model ranks weather compatibility for broad ecological guilds. It is a transparent field-planning heuristic. It is not a species-distribution model, a taxonomic identification system, an edibility guide, or proof that a fruiting body will occur.

## Daily inputs

The weather layer aggregates hourly Open-Meteo values into local calendar days:

- mean, minimum, and maximum air temperature
- precipitation total and maximum precipitation probability
- mean relative humidity and mean overnight humidity
- mean and maximum vapor-pressure deficit
- FAO reference evapotranspiration total
- mean and maximum wind and maximum gust
- mean cloud cover
- mean modeled soil temperature at 6 cm and 18 cm
- mean modeled volumetric soil moisture at 0–1, 1–3, 3–9, and 9–27 cm

## Thirty-day antecedent precipitation

For each target day, precipitation from the latest 30 days is weighted exponentially by age:

```text
weight(age) = 0.5 ^ (age / guild half-life)
weighted precipitation = Σ precipitation(age) × weight(age)
API30 equivalent = weighted precipitation × observed days / Σ weights
```

The app reports both the raw 30-day total and the recency-weighted API30 equivalent. Each guild has its own half-life, target, and saturation level.

## Soil-moisture profile and normalization

Each guild weights the four soil layers differently. Available layers are reweighted when one is missing.

The resulting profile is normalized against the latest 30 days:

```text
normalized soil moisture = (current - rolling p10) / (rolling p90 - rolling p10)
```

The value is clipped from 0 to 1. A minimum reference spread prevents a nearly constant model series from creating unstable divisions.

This is a **relative local anomaly**, not a universal volumetric-water threshold. It helps compare a grid with its own recent modeled condition.

## Temperature trend

The seven-day trend is the slope of a least-squares line fitted to daily mean air temperature:

```text
trend = degrees Fahrenheit per day
```

Morels reward gradual spring warming. Summer guilds prefer comparatively stable temperatures. Guild thresholds are in `config/guilds.yaml`.

## Growing degree-days

Daily degree-days are:

```text
GDD = max(daily mean temperature - guild base temperature, 0)
```

Mushroom Watch sums the latest guild-specific window, currently 21 or 30 days. This is a weather-timing indicator, not a validated fungal developmental clock.

## Atmospheric dry-down

A daily dry-down load combines normalized indicators:

```text
dry-down = 0.40 × VPD load
         + 0.25 × ET₀ load
         + 0.20 × wind load
         + 0.15 × low-humidity load
```

The displayed index is a recency-weighted three-day average. A guild-specific sensitivity converts it to a multiplier with a lower bound so the score remains interpretable.

## Base score

Each profile assigns 100 additive points across season and weather compatibility. Inputs are converted to 0–1 trapezoid scores: full credit inside the ideal interval, declining credit through a tolerance band, and zero outside the outer band.

Guild-specific penalties and proxies include:

- **Morels:** freeze penalty and strong soil-temperature/degree-day emphasis
- **Ectomycorrhizal fungi:** deeper soil-moisture weighting and high-VPD penalty
- **Wood-decay fungi:** recent rain/humidity proxies, partial soil-gate relief, and wind-exposure penalty
- **Soil/litter saprotrophs:** shallow-to-mid soil weighting, rain-pulse term, and freeze penalty

## Moisture as a limiting multiplier

The core 2.0 rule is:

```text
precipitation support = 0.65 × API30 support + 0.35 × 72-hour rain support
precipitation gate = 0.30 + 0.70 × precipitation support
moisture multiplier = min(soil gate, precipitation gate) × dry-down multiplier
final score = base score × moisture multiplier
```

The soil gate rises piecewise from severe limitation to full support. Because the lower of the soil and precipitation gates controls the result, accumulated rainfall cannot completely compensate for low modeled soil moisture, and wet soil cannot completely compensate for an extended precipitation deficit.

## Radius aggregation

Sample points use a golden-angle disk pattern with radial distance proportional to the square root of point index. This spreads points through the area of the radius rather than placing all points at the center or outer ring.

For each date and guild, the app reports:

- median, minimum, and maximum point score
- fraction of points at or above the user's favorable threshold
- evidence-confidence label

## Evidence-confidence labels

Point confidence combines:

- availability of critical input variables
- amount of available 30-day history
- forecast lead time
- reported hourly data coverage

Area confidence then combines median point confidence, agreement among point scores, and sample count.

Thresholds:

- **Higher data confidence:** at least 0.78
- **Moderate data confidence:** at least 0.55 and below 0.78
- **Low data confidence:** below 0.55

The label describes the evidence supporting the numerical weather score. It does not describe confidence in mushroom identification, edibility, habitat suitability, host presence, or actual fruiting.

## Recharge-event detection

For every forecast hour, the detector sums modeled liquid rain plus showers and examines rolling windows from 8 through 72 hours. It selects the shortest window that reaches the configured threshold, default 1.00 inch. Nearby threshold crossings are deduplicated. Events from multiple radius points are grouped by approximate start time and assigned an area fraction.

A recharge alert is independent from a fruiting-score alert. Rain can recharge a site before the temperature or biological delay is favorable.

## Known limitations

- Weather values are gridded estimates.
- Soil moisture is modeled and can be biased by soil type, canopy, slope, and land-cover mismatch.
- Wood moisture is not directly observed.
- Host trees, substrate, disturbance, and mycelial history are absent.
- The four guilds contain species with differing requirements.
- Degree-day and scoring thresholds are heuristics requiring field calibration.
- Forecast uncertainty grows with lead time; the confidence model only approximates this.
- A high score cannot establish presence or edibility.

## Calibration with observations

Use `found = false` observations as well as successful finds. Stratify by guild, region, habitat, substrate, and season. Evaluate false positives, missed flushes, calibration of score bands, and spatial consistency before changing thresholds. Change one parameter at a time and retain the previous profile in version control.
