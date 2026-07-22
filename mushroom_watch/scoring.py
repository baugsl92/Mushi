from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from .models import DailyGuildScore

SOIL_COLUMNS = [
    "soil_moisture_0_1",
    "soil_moisture_1_3",
    "soil_moisture_3_9",
    "soil_moisture_9_27",
]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def safe_float(value: Any, default: float = math.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def trapezoid_score(value: float, ideal: list[float] | tuple[float, float], *, lower_tolerance: float, upper_tolerance: float) -> float:
    if not math.isfinite(value):
        return 0.0
    ideal_low, ideal_high = map(float, ideal)
    if ideal_low <= value <= ideal_high:
        return 1.0
    if value < ideal_low:
        outer = ideal_low - float(lower_tolerance)
        return 0.0 if value <= outer else clamp((value - outer) / max(ideal_low - outer, 1e-9))
    outer = ideal_high + float(upper_tolerance)
    return 0.0 if value >= outer else clamp((outer - value) / max(outer - ideal_high, 1e-9))


def season_score(month: int, active_months: list[int], shoulder_months: list[int]) -> float:
    if month in active_months:
        return 1.0
    if month in shoulder_months:
        return 0.35
    return 0.0


def weighted_soil_moisture(frame: pd.DataFrame, profile: dict[str, Any]) -> pd.Series:
    weights = np.asarray(profile.get("soil_layer_weights", [0.1, 0.2, 0.4, 0.3]), dtype=float)
    if len(weights) != len(SOIL_COLUMNS) or weights.sum() <= 0:
        weights = np.asarray([0.1, 0.2, 0.4, 0.3], dtype=float)
    weights = weights / weights.sum()
    values = frame.reindex(columns=SOIL_COLUMNS).apply(pd.to_numeric, errors="coerce")
    available = values.notna().astype(float)
    numerator = values.fillna(0).mul(weights, axis=1).sum(axis=1)
    denominator = available.mul(weights, axis=1).sum(axis=1).replace(0, np.nan)
    return numerator / denominator


def normalize_soil_moisture(history: pd.Series, current: float, *, minimum_spread: float = 0.06) -> tuple[float, float, float]:
    clean = pd.to_numeric(history, errors="coerce").dropna()
    if not math.isfinite(current):
        return 0.0, math.nan, math.nan
    if len(clean) >= 8:
        low = float(clean.quantile(0.10))
        high = float(clean.quantile(0.90))
    elif len(clean) >= 2:
        low, high = float(clean.min()), float(clean.max())
    else:
        low, high = 0.12, 0.42
    if high - low < minimum_spread:
        midpoint = (high + low) / 2 if math.isfinite(high + low) else current
        low, high = midpoint - minimum_spread / 2, midpoint + minimum_spread / 2
    normalized = clamp((current - low) / max(high - low, 1e-9))
    return normalized, low, high


def antecedent_precipitation(frame: pd.DataFrame, index: int, *, days: int = 30, half_life_days: float = 9.0) -> tuple[float, float]:
    start = max(0, index - days + 1)
    values = pd.to_numeric(frame.loc[start:index, "precipitation_in"], errors="coerce").fillna(0).to_numpy(dtype=float)
    if len(values) == 0:
        return 0.0, 0.0
    ages = np.arange(len(values) - 1, -1, -1, dtype=float)
    weights = np.power(0.5, ages / max(float(half_life_days), 0.1))
    weighted = float(np.dot(values, weights))
    equivalent_30d = weighted * min(days, len(values)) / max(float(weights.sum()), 1e-9)
    return float(values.sum()), equivalent_30d


def temperature_trend(frame: pd.DataFrame, index: int, *, days: int = 7) -> float:
    start = max(0, index - days + 1)
    values = pd.to_numeric(frame.loc[start:index, "temperature_mean_f"], errors="coerce").dropna()
    if len(values) < 3:
        return 0.0
    x = np.arange(len(values), dtype=float)
    return float(np.polyfit(x, values.to_numpy(dtype=float), 1)[0])


def degree_days(frame: pd.DataFrame, index: int, profile: dict[str, Any]) -> tuple[float, int]:
    cfg = profile.get("temperature", {})
    base = float(cfg.get("gdd_base_f", 50))
    mode = str(cfg.get("gdd_mode", "rolling"))
    target_date = frame.loc[index, "date"]
    if mode == "seasonal":
        year = target_date.year
        eligible = frame.index[(frame.index <= index) & frame["date"].map(lambda item: item.year == year)].tolist()
        start = eligible[0] if eligible else index
        configured_window = int(cfg.get("gdd_window_days", 366))
        start = max(start, index - configured_window + 1)
    else:
        window = int(cfg.get("gdd_window_days", 30))
        start = max(0, index - window + 1)
    means = pd.to_numeric(frame.loc[start:index, "temperature_mean_f"], errors="coerce").dropna()
    total = float(np.maximum(means.to_numpy(dtype=float) - base, 0).sum())
    return total, int(len(means))


def daily_drydown_load(row: pd.Series) -> float:
    vpd = clamp((safe_float(row.get("vpd_mean_kpa"), 0.4) - 0.4) / 1.4)
    et0 = clamp((safe_float(row.get("et0_in"), 0.04) - 0.04) / 0.18)
    wind = clamp((safe_float(row.get("wind_speed_max_mph"), 8.0) - 8.0) / 20.0)
    humidity = clamp((75.0 - safe_float(row.get("relative_humidity_mean_pct"), 75.0)) / 40.0)
    return 0.40 * vpd + 0.25 * et0 + 0.20 * wind + 0.15 * humidity


def rolling_drydown_index(frame: pd.DataFrame, index: int) -> float:
    start = max(0, index - 2)
    loads = [daily_drydown_load(frame.loc[row_index]) for row_index in range(start, index + 1)]
    if not loads:
        return 0.0
    weights = np.asarray([0.2, 0.3, 0.5][-len(loads):], dtype=float)
    weights = weights / weights.sum()
    return clamp(float(np.dot(loads, weights)))


def confidence_label(value: float) -> str:
    if value >= 0.78:
        return "Higher data confidence"
    if value >= 0.55:
        return "Moderate data confidence"
    return "Low data confidence"


def _point_confidence(frame: pd.DataFrame, index: int) -> float:
    row = frame.loc[index]
    critical = [
        "temperature_mean_f", "precipitation_in", "overnight_humidity_mean_pct",
        "vpd_mean_kpa", "et0_in", "soil_temperature_6cm_f", "soil_moisture_3_9",
    ]
    coverage = float(pd.Series([row.get(column) for column in critical]).notna().mean())
    history_days = min(index + 1, 30)
    history_factor = history_days / 30.0
    target = row["date"]
    today = date.today()
    lead_days = max(0, (target - today).days)
    lead_factor = clamp(1.0 - 0.045 * lead_days, 0.55, 1.0)
    reported_coverage = safe_float(row.get("data_coverage"), coverage)
    return clamp(0.40 * coverage + 0.25 * history_factor + 0.20 * lead_factor + 0.15 * reported_coverage)


def _piecewise_soil_gate(normalized: float, floor: float, full: float) -> float:
    normalized = clamp(normalized)
    if normalized <= floor:
        return 0.15 + 0.35 * normalized / max(floor, 0.01)
    if normalized >= full:
        return 1.0
    return 0.50 + 0.50 * (normalized - floor) / max(full - floor, 0.01)


def _component_scores(frame: pd.DataFrame, index: int, profile: dict[str, Any], metrics: dict[str, float]) -> dict[str, float]:
    row = frame.loc[index]
    temp_cfg = profile["temperature"]
    weights = profile["weights"]
    air = safe_float(row.get("temperature_mean_f"))
    soil_values = np.asarray(
        [
            safe_float(row.get("soil_temperature_6cm_f")),
            safe_float(row.get("soil_temperature_18cm_f")),
        ],
        dtype=float,
    )
    soil_temp = float(np.nanmean(soil_values)) if np.isfinite(soil_values).any() else math.nan
    trend = metrics["temperature_trend_f_per_day"]
    gdd = metrics["degree_days"]
    humidity = safe_float(row.get("overnight_humidity_mean_pct"))
    recent = metrics["rain_72h_in"]
    ratios = {
        "season": season_score(row["date"].month, profile.get("active_months", []), profile.get("shoulder_months", [])),
        "air_temperature": trapezoid_score(air, temp_cfg["air_mean_ideal_f"], lower_tolerance=15, upper_tolerance=16),
        "soil_temperature": trapezoid_score(soil_temp, temp_cfg["soil_ideal_f"], lower_tolerance=12, upper_tolerance=14),
        "temperature_trend": trapezoid_score(trend, temp_cfg["trend_ideal_f_per_day"], lower_tolerance=1.5, upper_tolerance=1.5),
        "degree_days": trapezoid_score(gdd, temp_cfg["gdd_ideal"], lower_tolerance=max(50, temp_cfg["gdd_ideal"][0]), upper_tolerance=max(150, temp_cfg["gdd_ideal"][1] * 0.75)),
        "overnight_humidity": trapezoid_score(humidity, [78, 100], lower_tolerance=30, upper_tolerance=1),
        "rain_pulse": clamp(recent / max(float(profile["moisture"].get("recent_72h_target_in", 0.75)), 0.01)),
    }
    components = {name: ratios[name] * float(weight) for name, weight in weights.items()}
    model_type = profile.get("model_type")
    if model_type == "morel":
        hard_freeze = float(temp_cfg.get("hard_freeze_f", 27))
        low = safe_float(row.get("temperature_min_f"), 100)
        if low <= hard_freeze:
            components["hard_freeze_penalty"] = -20.0
    elif model_type == "ectomycorrhizal":
        # Ectomycorrhizal guilds are especially sensitive to hot, dry canopy conditions.
        vpd = safe_float(row.get("vpd_max_kpa"), 0)
        if vpd >= 2.2:
            components["high_vpd_penalty"] = -min(12.0, (vpd - 2.2) * 8.0)
    elif model_type == "wood_decay":
        # Wood substrate can buffer soil dryness, but hard drying winds still matter.
        gust = safe_float(row.get("wind_gust_max_mph"), 0)
        if gust >= 35:
            components["wind_exposure_penalty"] = -min(8.0, (gust - 35) * 0.4)
    elif model_type == "soil_saprotroph":
        low = safe_float(row.get("temperature_min_f"), 100)
        if low <= float(temp_cfg.get("hard_freeze_f", 27)):
            components["hard_freeze_penalty"] = -15.0
    return components


def score_guild_series(daily: pd.DataFrame, guild: str, profile: dict[str, Any]) -> list[DailyGuildScore]:
    frame = daily.copy().sort_values("date").reset_index(drop=True)
    if frame.empty:
        return []
    frame["soil_moisture_profile"] = weighted_soil_moisture(frame, profile)
    results: list[DailyGuildScore] = []
    moisture_cfg = profile["moisture"]
    for index, row in frame.iterrows():
        raw_30, api30 = antecedent_precipitation(
            frame, index, days=30, half_life_days=float(moisture_cfg.get("api_half_life_days", 9))
        )
        rain_72 = float(pd.to_numeric(frame.loc[max(0, index - 2):index, "precipitation_in"], errors="coerce").fillna(0).sum())
        trend = temperature_trend(frame, index)
        gdd, gdd_days = degree_days(frame, index, profile)
        current_soil = safe_float(row.get("soil_moisture_profile"))
        history = frame.loc[max(0, index - 29):index, "soil_moisture_profile"]
        soil_norm, soil_low, soil_high = normalize_soil_moisture(history, current_soil)
        drydown = rolling_drydown_index(frame, index)
        api_target = float(moisture_cfg.get("api30_target_in", 3.0))
        api_saturation = max(api_target, float(moisture_cfg.get("api30_saturation_in", api_target * 2)))
        api_support = clamp(api30 / max(api_target, 0.01))
        if api30 > api_target:
            api_support = 1.0 - 0.15 * clamp((api30 - api_saturation) / max(api_saturation, 0.01))
        recent_support = clamp(rain_72 / max(float(moisture_cfg.get("recent_72h_target_in", 0.75)), 0.01))
        precipitation_support = 0.65 * api_support + 0.35 * recent_support
        soil_gate = _piecewise_soil_gate(
            soil_norm,
            float(moisture_cfg.get("soil_norm_floor", 0.25)),
            float(moisture_cfg.get("soil_norm_full", 0.65)),
        )
        relief = float(moisture_cfg.get("soil_gate_relief", 0.0))
        soil_gate = clamp(soil_gate + relief)
        precipitation_gate = 0.30 + 0.70 * precipitation_support
        drydown_multiplier = clamp(
            1.0 - float(moisture_cfg.get("atmospheric_drydown_sensitivity", 0.7)) * 0.55 * drydown,
            0.35,
            1.0,
        )
        moisture_multiplier = clamp(min(soil_gate, precipitation_gate) * drydown_multiplier)
        metrics = {
            "antecedent_precip_30d_in": raw_30,
            "antecedent_precip_index_30d_in": api30,
            "rain_72h_in": rain_72,
            "soil_moisture_profile": current_soil,
            "soil_moisture_normalized": soil_norm,
            "soil_moisture_reference_low": soil_low,
            "soil_moisture_reference_high": soil_high,
            "temperature_trend_f_per_day": trend,
            "degree_days": gdd,
            "degree_day_history_days": gdd_days,
            "drydown_index": drydown,
            "soil_gate": soil_gate,
            "precipitation_gate": precipitation_gate,
            "drydown_multiplier": drydown_multiplier,
        }
        components = _component_scores(frame, index, profile, metrics)
        base_score = clamp(sum(components.values()) / 100.0) * 100.0
        final_score = base_score * moisture_multiplier
        confidence = _point_confidence(frame, index)
        reasons: list[str] = []
        if moisture_multiplier < 0.55:
            reasons.append("Moisture is limiting the otherwise favorable weather score.")
        if drydown >= 0.60:
            reasons.append("High VPD, evapotranspiration, wind, or low humidity indicate atmospheric dry-down.")
        if api30 < api_target * 0.70:
            reasons.append("Thirty-day antecedent precipitation is below the guild target.")
        if soil_norm < float(moisture_cfg.get("soil_norm_floor", 0.25)):
            reasons.append("Modeled soil moisture is low relative to its recent local range.")
        if profile.get("model_type") == "wood_decay":
            reasons.append("Wood moisture is not measured directly; soil moisture, rainfall, and humidity are proxies.")
        results.append(
            DailyGuildScore(
                date=row["date"],
                guild=guild,
                score=round(clamp(final_score, 0, 100), 1),
                base_score=round(clamp(base_score, 0, 100), 1),
                moisture_multiplier=round(moisture_multiplier, 3),
                drydown_index=round(drydown, 3),
                confidence_score=round(confidence, 3),
                confidence_label=confidence_label(confidence),
                components={name: round(value, 2) for name, value in components.items()},
                metrics={name: round(value, 4) if isinstance(value, float) and math.isfinite(value) else value for name, value in metrics.items()},
                reasons=reasons,
            )
        )
    return results


def score_lookup(scores: list[DailyGuildScore]) -> dict[date, DailyGuildScore]:
    return {item.date: item for item in scores}
