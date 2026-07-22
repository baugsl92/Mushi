from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mushroom_watch.scoring import (
    antecedent_precipitation,
    confidence_label,
    degree_days,
    normalize_soil_moisture,
    score_guild_series,
    temperature_trend,
)


def test_recent_rain_has_more_antecedent_weight_than_old_rain():
    old = pd.DataFrame({"precipitation_in": [1.0] + [0.0] * 29})
    recent = pd.DataFrame({"precipitation_in": [0.0] * 29 + [1.0]})
    old_raw, old_api = antecedent_precipitation(old, 29, days=30, half_life_days=8)
    recent_raw, recent_api = antecedent_precipitation(recent, 29, days=30, half_life_days=8)
    assert old_raw == recent_raw == pytest.approx(1.0)
    assert recent_api > old_api * 5


def test_soil_normalization_uses_recent_local_range():
    history = pd.Series(np.linspace(0.10, 0.40, 30))
    normalized, low, high = normalize_soil_moisture(history, 0.25)
    assert 0 < normalized < 1
    assert low < 0.25 < high


def test_temperature_trend_and_degree_days_are_computed(weather_frame, profiles):
    trend = temperature_trend(weather_frame, len(weather_frame) - 1, days=7)
    assert trend == pytest.approx(0.25, abs=0.01)
    gdd, days = degree_days(weather_frame, len(weather_frame) - 1, profiles["morel"])
    expected = sum(max(value - 40, 0) for value in weather_frame["temperature_mean_f"].tail(30))
    assert gdd == pytest.approx(expected)
    assert days == 30


def test_moisture_is_a_limiting_multiplier(weather_frame, profiles):
    wet = weather_frame.copy()
    wet["precipitation_in"] = 0.18
    for column in ["soil_moisture_0_1", "soil_moisture_1_3", "soil_moisture_3_9", "soil_moisture_9_27"]:
        wet[column] = np.linspace(0.18, 0.42, len(wet))
    wet["vpd_mean_kpa"] = 0.45
    wet["et0_in"] = 0.04
    wet["wind_speed_max_mph"] = 6
    wet["relative_humidity_mean_pct"] = 80

    dry = wet.copy()
    dry["precipitation_in"] = 0.0
    for column in ["soil_moisture_0_1", "soil_moisture_1_3", "soil_moisture_3_9", "soil_moisture_9_27"]:
        dry[column] = np.linspace(0.40, 0.10, len(dry))
    dry["vpd_mean_kpa"] = 2.2
    dry["et0_in"] = 0.24
    dry["wind_speed_max_mph"] = 30
    dry["relative_humidity_mean_pct"] = 35

    wet_score = score_guild_series(wet, "morel", profiles["morel"])[-1]
    dry_score = score_guild_series(dry, "morel", profiles["morel"])[-1]

    assert wet_score.score <= wet_score.base_score
    assert dry_score.score <= dry_score.base_score
    assert dry_score.moisture_multiplier < 0.35
    assert wet_score.moisture_multiplier > dry_score.moisture_multiplier
    assert wet_score.score > dry_score.score
    assert any("Moisture is limiting" in reason for reason in dry_score.reasons)


def test_same_weather_produces_distinct_guild_models(weather_frame, profiles):
    final_scores = {
        guild: score_guild_series(weather_frame, guild, profile)[-1].score
        for guild, profile in profiles.items()
    }
    assert len(set(final_scores.values())) >= 3


def test_confidence_labels_are_stable():
    assert confidence_label(0.90) == "Higher data confidence"
    assert confidence_label(0.60) == "Moderate data confidence"
    assert confidence_label(0.20) == "Low data confidence"
