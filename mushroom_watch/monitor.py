from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .analysis import analyze_guild
from .config import resolve_watch_location
from .geo import CountyCatalog, sample_radius
from .models import AlertDecision, AggregateGuildScore, PointWeather, RechargeEvent
from .recharge import aggregate_recharge_events, find_recharge_events
from .weather import fetch_weather_points


def local_now(timezone_name: str) -> datetime:
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return datetime.now()
    return datetime.now(zone).replace(tzinfo=None)


def run_watch_analysis(
    watch: dict[str, Any],
    *,
    county_catalog: CountyCatalog,
    profiles: dict[str, dict[str, Any]],
    weather_fetcher: Callable[..., list[PointWeather]] = fetch_weather_points,
) -> dict[str, Any]:
    location = resolve_watch_location(watch["location"], county_catalog)
    radius = float(watch.get("radius_miles", 20))
    sample_count = int(watch.get("sample_points", 9))
    forecast_days = int(watch.get("forecast_days", 7))
    threshold = float(watch.get("score_threshold", 70))
    points = sample_radius(location.latitude, location.longitude, radius, sample_count)
    weather_points = weather_fetcher(points, past_days=30, forecast_days=forecast_days + 1)
    timezone_name = weather_points[0].timezone if weather_points else location.timezone
    now = local_now(timezone_name)
    today = now.date()

    guild_results: dict[str, dict[str, Any]] = {}
    for guild in watch.get("guilds", []):
        if guild not in profiles:
            continue
        point_scores, aggregates = analyze_guild(
            weather_points, guild, profiles[guild], threshold=threshold
        )
        guild_results[guild] = {"point_scores": point_scores, "aggregates": aggregates}

    recharge_threshold = float(watch.get("recharge_threshold_inches", 1.0))
    events_by_point = {
        item.point.point_id: find_recharge_events(
            item.hourly,
            threshold_inches=recharge_threshold,
            minimum_hours=8,
            maximum_hours=72,
            now=now,
        )
        for item in weather_points
    }
    recharge_events = aggregate_recharge_events(events_by_point, total_points=len(weather_points))
    return {
        "location": location,
        "points": points,
        "weather_points": weather_points,
        "guild_results": guild_results,
        "recharge_events": recharge_events,
        "today": today,
        "now": now,
        "timezone": timezone_name,
    }


def fruiting_decisions(
    watch: dict[str, Any],
    analysis: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> list[AlertDecision]:
    threshold = float(watch.get("score_threshold", 70))
    minimum_area = float(watch.get("minimum_area_fraction", 0.40))
    minimum_confidence = float(watch.get("minimum_confidence", 0.45))
    forecast_days = int(watch.get("forecast_days", 7))
    today: date = analysis["today"]
    decisions: list[AlertDecision] = []
    for guild, result in analysis["guild_results"].items():
        eligible: list[AggregateGuildScore] = [
            item for item in result["aggregates"]
            if today <= item.date and (item.date - today).days <= forecast_days
        ]
        if not eligible:
            continue
        best = max(eligible, key=lambda item: (item.median_score, item.favorable_fraction))
        if best.median_score < threshold or best.favorable_fraction < minimum_area:
            continue
        if best.confidence_score < minimum_confidence:
            continue
        profile = profiles[guild]
        title = f"🍄 {profile['display_name']} window"
        message = (
            f"**{watch['name']}** peaks at **{best.median_score:.0f}/100** on "
            f"**{best.date:%a %b %d}**.\n\n"
            f"Favorable across **{best.favorable_fraction * 100:.0f}%** of sampled grids. "
            f"{best.confidence_label}.\n\n"
            "Weather compatibility is not proof of presence or edibility."
        )
        decisions.append(
            AlertDecision(
                watch_name=str(watch["name"]),
                alert_type="fruiting",
                key=f"fruiting:{watch['name']}:{guild}:{best.date.isoformat()}",
                title=title,
                message=message,
                priority=4 if best.median_score >= 82 else 3,
                tags=("mushroom", "chart_with_upwards_trend"),
                event_time=datetime.combine(best.date, datetime.min.time()),
                metadata={
                    "guild": guild,
                    "score": best.median_score,
                    "area_fraction": best.favorable_fraction,
                    "confidence": best.confidence_score,
                },
            )
        )
    return decisions


def recharge_decisions(watch: dict[str, Any], analysis: dict[str, Any]) -> list[AlertDecision]:
    minimum_area = float(watch.get("recharge_minimum_area_fraction", 0.35))
    threshold = float(watch.get("recharge_threshold_inches", 1.0))
    decisions: list[AlertDecision] = []
    for event in analysis["recharge_events"]:
        if event.precipitation_in < threshold or event.sample_fraction < minimum_area:
            continue
        probability = (
            f" Peak modeled probability: {event.peak_probability_pct:.0f}%."
            if event.peak_probability_pct is not None else ""
        )
        message = (
            f"**{watch['name']}** has a modeled recharge event of about "
            f"**{event.precipitation_in:.2f} in** over **{event.duration_hours} hours**, "
            f"from **{event.start:%a %b %d %I %p}** to **{event.end:%a %b %d %I %p}**.\n\n"
            f"The event appears in **{event.sample_fraction * 100:.0f}%** of sampled grids.{probability}"
        )
        decisions.append(
            AlertDecision(
                watch_name=str(watch["name"]),
                alert_type="recharge",
                key=f"recharge:{watch['name']}:{event.start:%Y%m%d%H}",
                title="🌧️ Mushroom recharge event",
                message=message,
                priority=4,
                tags=("rain_cloud", "mushroom"),
                event_time=event.start,
                metadata={
                    "precipitation_in": event.precipitation_in,
                    "duration_hours": event.duration_hours,
                    "area_fraction": event.sample_fraction,
                },
            )
        )
    return decisions
