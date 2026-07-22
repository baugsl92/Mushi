from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from .models import AggregateGuildScore, DailyGuildScore, PointWeather
from .scoring import confidence_label, score_guild_series


def score_points_for_guild(
    weather_points: list[PointWeather],
    guild: str,
    profile: dict[str, Any],
) -> dict[str, list[DailyGuildScore]]:
    return {
        item.point.point_id: score_guild_series(item.daily, guild, profile)
        for item in weather_points
    }


def aggregate_point_scores(
    point_scores: dict[str, list[DailyGuildScore]],
    *,
    threshold: float,
) -> list[AggregateGuildScore]:
    by_date: dict[date, list[DailyGuildScore]] = defaultdict(list)
    for scores in point_scores.values():
        for score in scores:
            by_date[score.date].append(score)
    aggregates: list[AggregateGuildScore] = []
    for target_date in sorted(by_date):
        rows = by_date[target_date]
        values = np.asarray([row.score for row in rows], dtype=float)
        confidences = np.asarray([row.confidence_score for row in rows], dtype=float)
        agreement = 1.0 - min(float(values.std(ddof=0)) / 35.0, 1.0) if len(values) > 1 else 1.0
        sample_factor = min(len(values) / 9.0, 1.0)
        combined_confidence = float(0.60 * np.median(confidences) + 0.25 * agreement + 0.15 * sample_factor)
        favorable_fraction = float(np.mean(values >= threshold))
        reasons: list[str] = []
        spread = float(values.max() - values.min())
        if spread >= 25:
            reasons.append("Scores vary widely across the radius, likely reflecting localized rain or terrain-scale model differences.")
        if favorable_fraction < 0.40:
            reasons.append("Favorable conditions are limited to a minority of sampled weather grids.")
        aggregates.append(
            AggregateGuildScore(
                date=target_date,
                guild=rows[0].guild,
                median_score=round(float(np.median(values)), 1),
                minimum_score=round(float(values.min()), 1),
                maximum_score=round(float(values.max()), 1),
                favorable_fraction=round(favorable_fraction, 3),
                confidence_score=round(combined_confidence, 3),
                confidence_label=confidence_label(combined_confidence),
                point_count=len(values),
                reasons=reasons,
            )
        )
    return aggregates


def analyze_guild(
    weather_points: list[PointWeather],
    guild: str,
    profile: dict[str, Any],
    *,
    threshold: float,
) -> tuple[dict[str, list[DailyGuildScore]], list[AggregateGuildScore]]:
    point_scores = score_points_for_guild(weather_points, guild, profile)
    return point_scores, aggregate_point_scores(point_scores, threshold=threshold)


def aggregate_frame(aggregates: list[AggregateGuildScore]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": item.date,
                "guild": item.guild,
                "median_score": item.median_score,
                "minimum_score": item.minimum_score,
                "maximum_score": item.maximum_score,
                "favorable_fraction": item.favorable_fraction,
                "confidence_score": item.confidence_score,
                "confidence_label": item.confidence_label,
                "point_count": item.point_count,
            }
            for item in aggregates
        ]
    )


def point_map_frame(
    weather_points: list[PointWeather],
    point_scores: dict[str, list[DailyGuildScore]],
    target_date: date,
) -> pd.DataFrame:
    rows = []
    score_lookup = {
        point_id: {score.date: score for score in scores}
        for point_id, scores in point_scores.items()
    }
    for item in weather_points:
        score = score_lookup.get(item.point.point_id, {}).get(target_date)
        if score is None:
            continue
        rows.append(
            {
                "point_id": item.point.point_id,
                "latitude": item.point.latitude,
                "longitude": item.point.longitude,
                "score": score.score,
                "confidence": score.confidence_label,
                "distance_miles": item.point.distance_miles,
            }
        )
    return pd.DataFrame(rows)


def representative_detail(
    point_scores: dict[str, list[DailyGuildScore]], target_date: date
) -> DailyGuildScore | None:
    candidates = [
        score
        for scores in point_scores.values()
        for score in scores
        if score.date == target_date
    ]
    if not candidates:
        return None
    target = median([score.score for score in candidates])
    return min(candidates, key=lambda score: abs(score.score - target))
