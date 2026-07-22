from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from mushroom_watch.config import WatchConfigError, dump_watch_config, load_watch_config
from mushroom_watch.models import AggregateGuildScore, RechargeEvent
from mushroom_watch.monitor import fruiting_decisions, recharge_decisions


def test_watch_config_round_trip(tmp_path: Path):
    watch = {
        "name": "Test",
        "location": {"mode": "coordinates", "latitude": 41.6, "longitude": -85.0},
        "guilds": ["morel"],
    }
    path = tmp_path / "watch.yaml"
    path.write_text(dump_watch_config(watch), encoding="utf-8")
    assert load_watch_config(path) == [watch]


def test_invalid_watch_config_is_rejected(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("watches: []\n", encoding="utf-8")
    with pytest.raises(WatchConfigError):
        load_watch_config(path)


def test_fruiting_and_recharge_decisions(profiles):
    today = date(2026, 7, 22)
    aggregate = AggregateGuildScore(
        date=today + timedelta(days=2),
        guild="ectomycorrhizal",
        median_score=82,
        minimum_score=70,
        maximum_score=91,
        favorable_fraction=0.70,
        confidence_score=0.80,
        confidence_label="Higher data confidence",
        point_count=9,
    )
    watch = {
        "name": "Test woods",
        "score_threshold": 68,
        "minimum_area_fraction": 0.40,
        "minimum_confidence": 0.45,
        "forecast_days": 7,
        "recharge_threshold_inches": 1.0,
        "recharge_minimum_area_fraction": 0.35,
    }
    analysis = {
        "today": today,
        "guild_results": {"ectomycorrhizal": {"aggregates": [aggregate]}},
        "recharge_events": [
            RechargeEvent(
                start=datetime(2026, 7, 23, 8),
                end=datetime(2026, 7, 24, 8),
                duration_hours=24,
                precipitation_in=1.25,
                peak_probability_pct=85,
                sample_fraction=0.60,
            )
        ],
    }
    fruit = fruiting_decisions(watch, analysis, profiles)
    rain = recharge_decisions(watch, analysis)
    assert len(fruit) == 1
    assert "82/100" in fruit[0].message
    assert len(rain) == 1
    assert "1.25 in" in rain[0].message
