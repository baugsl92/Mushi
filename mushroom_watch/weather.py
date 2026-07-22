from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import requests

from .models import PointWeather, SamplePoint

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation",
    "rain",
    "showers",
    "precipitation_probability",
    "vapour_pressure_deficit",
    "et0_fao_evapotranspiration",
    "wind_speed_10m",
    "wind_gusts_10m",
    "cloud_cover",
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_moisture_0_to_1cm",
    "soil_moisture_1_to_3cm",
    "soil_moisture_3_to_9cm",
    "soil_moisture_9_to_27cm",
]

COLUMN_MAP = {
    "temperature_2m": "temperature_f",
    "relative_humidity_2m": "relative_humidity_pct",
    "dew_point_2m": "dew_point_f",
    "precipitation": "precipitation_in",
    "rain": "rain_in",
    "showers": "showers_in",
    "precipitation_probability": "precip_probability_pct",
    "vapour_pressure_deficit": "vpd_kpa",
    "et0_fao_evapotranspiration": "et0_in",
    "wind_speed_10m": "wind_speed_mph",
    "wind_gusts_10m": "wind_gust_mph",
    "cloud_cover": "cloud_cover_pct",
    "soil_temperature_6cm": "soil_temperature_6cm_f",
    "soil_temperature_18cm": "soil_temperature_18cm_f",
    "soil_moisture_0_to_1cm": "soil_moisture_0_1",
    "soil_moisture_1_to_3cm": "soil_moisture_1_3",
    "soil_moisture_3_to_9cm": "soil_moisture_3_9",
    "soil_moisture_9_to_27cm": "soil_moisture_9_27",
}


class WeatherError(RuntimeError):
    """Raised when Open-Meteo data cannot be retrieved or parsed."""


def _values(payload: dict[str, Any], key: str, length: int) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        return [None] * length
    if len(value) < length:
        return value + [None] * (length - len(value))
    return value[:length]


def aggregate_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    if hourly.empty:
        return pd.DataFrame()
    frame = hourly.copy()
    frame["date"] = frame["time"].dt.date
    frame["hour"] = frame["time"].dt.hour
    frame["night_humidity"] = frame["relative_humidity_pct"].where((frame["hour"] <= 7) | (frame["hour"] >= 20))
    aggregations = {
        "temperature_mean_f": ("temperature_f", "mean"),
        "temperature_max_f": ("temperature_f", "max"),
        "temperature_min_f": ("temperature_f", "min"),
        "precipitation_in": ("precipitation_in", "sum"),
        "rain_in": ("rain_in", "sum"),
        "showers_in": ("showers_in", "sum"),
        "precip_probability_max_pct": ("precip_probability_pct", "max"),
        "relative_humidity_mean_pct": ("relative_humidity_pct", "mean"),
        "overnight_humidity_mean_pct": ("night_humidity", "mean"),
        "vpd_mean_kpa": ("vpd_kpa", "mean"),
        "vpd_max_kpa": ("vpd_kpa", "max"),
        "et0_in": ("et0_in", "sum"),
        "wind_speed_mean_mph": ("wind_speed_mph", "mean"),
        "wind_speed_max_mph": ("wind_speed_mph", "max"),
        "wind_gust_max_mph": ("wind_gust_mph", "max"),
        "cloud_cover_mean_pct": ("cloud_cover_pct", "mean"),
        "soil_temperature_6cm_f": ("soil_temperature_6cm_f", "mean"),
        "soil_temperature_18cm_f": ("soil_temperature_18cm_f", "mean"),
        "soil_moisture_0_1": ("soil_moisture_0_1", "mean"),
        "soil_moisture_1_3": ("soil_moisture_1_3", "mean"),
        "soil_moisture_3_9": ("soil_moisture_3_9", "mean"),
        "soil_moisture_9_27": ("soil_moisture_9_27", "mean"),
        "hour_count": ("time", "count"),
    }
    daily = frame.groupby("date", as_index=False).agg(**aggregations)
    data_columns = [
        "temperature_f", "precipitation_in", "relative_humidity_pct", "vpd_kpa",
        "et0_in", "soil_temperature_6cm_f", "soil_moisture_3_9",
    ]
    available = frame[data_columns].notna().sum(axis=1) / len(data_columns)
    coverage = frame.assign(_coverage=available).groupby("date", as_index=False)["_coverage"].mean()
    daily = daily.merge(coverage, on="date", how="left").rename(columns={"_coverage": "data_coverage"})
    numeric = [column for column in daily.columns if column != "date"]
    daily[numeric] = daily[numeric].apply(pd.to_numeric, errors="coerce")
    return daily.sort_values("date").reset_index(drop=True)


def parse_weather_payload(payload: dict[str, Any], point: SamplePoint) -> PointWeather:
    if payload.get("error"):
        raise WeatherError(str(payload.get("reason") or "Open-Meteo returned an error."))
    hourly_payload = payload.get("hourly") or {}
    raw_times = hourly_payload.get("time") or []
    if not raw_times:
        raise WeatherError(f"No hourly weather data were returned for {point.point_id}.")
    frame = pd.DataFrame({"time": pd.to_datetime(raw_times, errors="coerce")})
    for api_name, column_name in COLUMN_MAP.items():
        frame[column_name] = _values(hourly_payload, api_name, len(frame))
    numeric = [column for column in frame.columns if column != "time"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    return PointWeather(
        point=point,
        timezone=str(payload.get("timezone") or "auto"),
        hourly=frame,
        daily=aggregate_daily(frame),
    )


def fetch_weather_points(
    points: Sequence[SamplePoint],
    *,
    past_days: int = 30,
    forecast_days: int = 8,
    session: requests.Session | None = None,
) -> list[PointWeather]:
    if not points:
        raise ValueError("At least one sample point is required.")
    client = session or requests.Session()
    params = {
        "latitude": ",".join(f"{point.latitude:.6f}" for point in points),
        "longitude": ",".join(f"{point.longitude:.6f}" for point in points),
        "hourly": ",".join(HOURLY_VARIABLES),
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "wind_speed_unit": "mph",
        "timezone": "auto",
        "past_days": max(30, min(int(past_days), 92)),
        "forecast_days": max(1, min(int(forecast_days), 16)),
        "cell_selection": "land",
    }
    response = client.get(FORECAST_URL, params=params, timeout=60)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise WeatherError(f"Weather service error: {response.text[:500]}") from exc
    payload: Any = response.json()
    payloads = payload if isinstance(payload, list) else [payload]
    if len(payloads) != len(points):
        raise WeatherError(f"Expected {len(points)} weather responses, received {len(payloads)}.")
    return [parse_weather_payload(item, point) for item, point in zip(payloads, points, strict=True)]


def synthetic_weather_frame(days: int = 40, *, start: str = "2026-04-01") -> pd.DataFrame:
    """Small deterministic fixture helper used by examples and tests."""
    dates = pd.date_range(start, periods=days, freq="D")
    index = np.arange(days)
    return pd.DataFrame(
        {
            "date": dates.date,
            "temperature_mean_f": 50 + index * 0.25,
            "temperature_max_f": 58 + index * 0.25,
            "temperature_min_f": 42 + index * 0.25,
            "precipitation_in": np.where(index % 6 == 0, 0.65, 0.03),
            "precip_probability_max_pct": 40,
            "relative_humidity_mean_pct": 72,
            "overnight_humidity_mean_pct": 84,
            "vpd_mean_kpa": 0.65,
            "vpd_max_kpa": 1.1,
            "et0_in": 0.08,
            "wind_speed_mean_mph": 6,
            "wind_speed_max_mph": 12,
            "wind_gust_max_mph": 18,
            "cloud_cover_mean_pct": 55,
            "soil_temperature_6cm_f": 48 + index * 0.18,
            "soil_temperature_18cm_f": 47 + index * 0.14,
            "soil_moisture_0_1": 0.23,
            "soil_moisture_1_3": 0.25,
            "soil_moisture_3_9": 0.28,
            "soil_moisture_9_27": 0.30,
            "hour_count": 24,
            "data_coverage": 1.0,
        }
    )
