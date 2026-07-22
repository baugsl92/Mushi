from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from mushroom_watch.models import RechargeEvent
from mushroom_watch.recharge import aggregate_recharge_events, find_recharge_events


def hourly_frame(start: datetime, precipitation: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range(start, periods=len(precipitation), freq="h"),
            "precipitation_in": precipitation,
            "precip_probability_pct": [80.0] * len(precipitation),
        }
    )


def test_finds_shortest_qualifying_window_between_8_and_72_hours():
    now = datetime(2026, 7, 22, 8)
    precipitation = [0.10] * 10 + [0.0] * 90
    events = find_recharge_events(hourly_frame(now, precipitation), now=now)
    assert len(events) == 1
    assert events[0].precipitation_in == pytest.approx(1.0)
    assert events[0].duration_hours == 10
    assert events[0].start == now
    assert events[0].end == now + timedelta(hours=10)


def test_liquid_rain_and_showers_take_precedence_over_snow_precipitation():
    now = datetime(2026, 7, 22, 8)
    frame = hourly_frame(now, [0.20] * 12)
    frame["rain_in"] = [0.04] * 12
    frame["showers_in"] = [0.01] * 12
    assert find_recharge_events(frame, now=now) == []


def test_does_not_alert_below_one_inch():
    now = datetime(2026, 7, 22, 8)
    events = find_recharge_events(hourly_frame(now, [0.01] * 72), now=now)
    assert events == []


def test_spatial_aggregation_reports_area_without_expanding_window():
    start = datetime(2026, 7, 23, 6)
    events_by_point = {
        "center": [RechargeEvent(start, start + timedelta(hours=12), 12, 1.1, 90)],
        "p01": [RechargeEvent(start + timedelta(hours=2), start + timedelta(hours=16), 14, 1.3, 85)],
        "p02": [],
    }
    events = aggregate_recharge_events(events_by_point, total_points=3)
    assert len(events) == 1
    assert events[0].sample_fraction == pytest.approx(2 / 3)
    assert 8 <= events[0].duration_hours <= 72
    assert events[0].precipitation_in == pytest.approx(1.3)
