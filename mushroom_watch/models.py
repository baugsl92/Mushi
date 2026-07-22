from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class Location:
    label: str
    latitude: float
    longitude: float
    timezone: str = "auto"
    state_abbr: str | None = None
    county_name: str | None = None
    source: str = "custom"


@dataclass(frozen=True)
class SamplePoint:
    point_id: str
    latitude: float
    longitude: float
    distance_miles: float
    bearing_degrees: float


@dataclass
class PointWeather:
    point: SamplePoint
    timezone: str
    hourly: Any
    daily: Any


@dataclass(frozen=True)
class RechargeEvent:
    start: datetime
    end: datetime
    duration_hours: int
    precipitation_in: float
    peak_probability_pct: float | None = None
    sample_fraction: float = 1.0


@dataclass
class DailyGuildScore:
    date: date
    guild: str
    score: float
    base_score: float
    moisture_multiplier: float
    drydown_index: float
    confidence_score: float
    confidence_label: str
    components: dict[str, float]
    metrics: dict[str, float | int | str | None]
    reasons: list[str] = field(default_factory=list)


@dataclass
class AggregateGuildScore:
    date: date
    guild: str
    median_score: float
    minimum_score: float
    maximum_score: float
    favorable_fraction: float
    confidence_score: float
    confidence_label: str
    point_count: int
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AlertDecision:
    watch_name: str
    alert_type: str
    key: str
    title: str
    message: str
    priority: int
    tags: tuple[str, ...]
    event_time: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
