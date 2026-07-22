from __future__ import annotations

import pandas as pd
import pytest

from mushroom_watch.models import SamplePoint
from mushroom_watch.weather import COLUMN_MAP, aggregate_daily, fetch_weather_points, parse_weather_payload


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.text = "ok"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.last_params = None

    def get(self, url, params, timeout):
        self.last_params = params
        return FakeResponse(self.payload)


def make_payload(start="2026-07-20 00:00", hours=48):
    times = pd.date_range(start, periods=hours, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()
    hourly = {"time": times}
    defaults = {
        "temperature_2m": 65.0,
        "relative_humidity_2m": 80.0,
        "dew_point_2m": 58.0,
        "precipitation": 0.05,
        "rain": 0.04,
        "showers": 0.01,
        "precipitation_probability": 70.0,
        "vapour_pressure_deficit": 0.6,
        "et0_fao_evapotranspiration": 0.002,
        "wind_speed_10m": 7.0,
        "wind_gusts_10m": 12.0,
        "cloud_cover": 60.0,
        "soil_temperature_6cm": 62.0,
        "soil_temperature_18cm": 60.0,
        "soil_moisture_0_to_1cm": 0.25,
        "soil_moisture_1_to_3cm": 0.27,
        "soil_moisture_3_to_9cm": 0.30,
        "soil_moisture_9_to_27cm": 0.32,
    }
    for key in COLUMN_MAP:
        hourly[key] = [defaults[key]] * hours
    return {"timezone": "America/Detroit", "hourly": hourly}


def test_payload_parsing_and_daily_aggregation():
    point = SamplePoint("center", 41.6, -85.0, 0, 0)
    weather = parse_weather_payload(make_payload(), point)
    assert weather.timezone == "America/Detroit"
    assert len(weather.hourly) == 48
    assert len(weather.daily) == 2
    assert weather.daily.loc[0, "precipitation_in"] == pytest.approx(1.2)
    assert weather.daily.loc[0, "hour_count"] == 24
    assert weather.daily.loc[0, "data_coverage"] == pytest.approx(1.0)


def test_multi_point_fetch_uses_30_day_minimum_and_parses_list():
    points = [
        SamplePoint("center", 41.6, -85.0, 0, 0),
        SamplePoint("p01", 41.7, -85.1, 10, 90),
    ]
    session = FakeSession([make_payload(), make_payload()])
    result = fetch_weather_points(points, past_days=5, forecast_days=99, session=session)
    assert len(result) == 2
    assert session.last_params["past_days"] == 30
    assert session.last_params["forecast_days"] == 16
    assert session.last_params["cell_selection"] == "land"
