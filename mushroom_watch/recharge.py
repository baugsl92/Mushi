from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from .models import RechargeEvent


def find_recharge_events(
    hourly: pd.DataFrame,
    *,
    threshold_inches: float = 1.0,
    minimum_hours: int = 8,
    maximum_hours: int = 72,
    now: datetime | None = None,
    merge_gap_hours: int = 8,
) -> list[RechargeEvent]:
    """Find earliest threshold crossings in every rolling 8-72 hour window."""
    if hourly.empty:
        return []
    if minimum_hours < 1 or maximum_hours < minimum_hours:
        raise ValueError("Recharge window bounds are invalid.")
    liquid_columns = [column for column in ["rain_in", "showers_in"] if column in hourly]
    columns = [column for column in ["time", "precipitation_in", "rain_in", "showers_in", "precip_probability_pct"] if column in hourly]
    frame = hourly[columns].copy()
    if liquid_columns and frame[liquid_columns].apply(pd.to_numeric, errors="coerce").notna().any().any():
        frame["precipitation_in"] = (
            frame[liquid_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        )
    if "precipitation_in" not in frame:
        raise ValueError("Hourly data require rain/showers or precipitation values.")
    if "precip_probability_pct" not in frame:
        frame["precip_probability_pct"] = None
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    frame["precipitation_in"] = pd.to_numeric(frame["precipitation_in"], errors="coerce").fillna(0).clip(lower=0)
    frame["precip_probability_pct"] = pd.to_numeric(frame["precip_probability_pct"], errors="coerce")
    frame = frame.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    if now is not None:
        cutoff = pd.Timestamp(now)
        frame = frame[frame["time"] >= cutoff].reset_index(drop=True)
    if len(frame) < minimum_hours:
        return []
    precipitation = frame["precipitation_in"].to_numpy(dtype=float)
    cumulative = precipitation.cumsum()
    candidates: list[RechargeEvent] = []
    for end_index in range(minimum_hours - 1, len(frame)):
        max_duration = min(maximum_hours, end_index + 1)
        for duration in range(minimum_hours, max_duration + 1):
            start_index = end_index - duration + 1
            before = cumulative[start_index - 1] if start_index > 0 else 0.0
            total = float(cumulative[end_index] - before)
            if total + 1e-9 < threshold_inches:
                continue
            probability = frame.loc[start_index:end_index, "precip_probability_pct"].max()
            candidates.append(
                RechargeEvent(
                    start=frame.loc[start_index, "time"].to_pydatetime(),
                    end=(frame.loc[end_index, "time"] + pd.Timedelta(hours=1)).to_pydatetime(),
                    duration_hours=duration,
                    precipitation_in=round(total, 3),
                    peak_probability_pct=None if pd.isna(probability) else float(probability),
                )
            )
            break
    if not candidates:
        return []
    selected: list[RechargeEvent] = []
    gap = timedelta(hours=merge_gap_hours)
    for candidate in candidates:
        if selected and candidate.start <= selected[-1].end + gap:
            continue
        selected.append(candidate)
    return selected


def aggregate_recharge_events(
    events_by_point: dict[str, list[RechargeEvent]],
    *,
    total_points: int,
    grouping_hours: int = 12,
) -> list[RechargeEvent]:
    """Group point events by approximate start time and report spatial coverage."""
    rows: list[tuple[str, RechargeEvent]] = [
        (point_id, event) for point_id, events in events_by_point.items() for event in events
    ]
    rows.sort(key=lambda item: item[1].start)
    groups: list[list[tuple[str, RechargeEvent]]] = []
    tolerance = timedelta(hours=grouping_hours)
    for row in rows:
        if not groups or row[1].start > min(item[1].start for item in groups[-1]) + tolerance:
            groups.append([row])
        else:
            groups[-1].append(row)
    aggregated: list[RechargeEvent] = []
    for group in groups:
        unique_points = {point_id for point_id, _ in group}
        ordered_events = sorted((event for _, event in group), key=lambda event: (event.start, event.duration_hours))
        representative = ordered_events[len(ordered_events) // 2]
        totals = sorted(event.precipitation_in for event in ordered_events)
        probabilities = [event.peak_probability_pct for event in ordered_events if event.peak_probability_pct is not None]
        median_total = totals[len(totals) // 2]
        aggregated.append(
            RechargeEvent(
                start=representative.start,
                end=representative.end,
                duration_hours=max(8, min(72, representative.duration_hours)),
                precipitation_in=round(median_total, 3),
                peak_probability_pct=max(probabilities) if probabilities else representative.peak_probability_pct,
                sample_fraction=len(unique_points) / max(total_points, 1),
            )
        )
    return aggregated
