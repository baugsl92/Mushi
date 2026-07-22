from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from .models import Location, SamplePoint

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
EARTH_RADIUS_MILES = 3958.7613
GOLDEN_ANGLE_DEGREES = 137.50776405003785

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}


class LocationError(RuntimeError):
    """Raised when a location cannot be resolved."""


@dataclass(frozen=True)
class CountyRecord:
    fips: str
    state_abbr: str
    state_name: str
    county_name: str
    latitude: float
    longitude: float

    @property
    def label(self) -> str:
        suffix = self.county_name
        if not suffix.lower().endswith(("county", "parish", "borough", "municipality", "census area")):
            suffix = f"{suffix} County"
        return f"{suffix}, {self.state_name}"


class CountyCatalog:
    def __init__(self, frame: pd.DataFrame):
        required = {"fips", "state_abbr", "county_name", "latitude", "longitude"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"County catalog is missing columns: {sorted(missing)}")
        clean = frame.copy()
        clean["state_abbr"] = clean["state_abbr"].astype(str).str.upper()
        clean["fips"] = clean["fips"].astype(str).str.zfill(5)
        clean = clean[clean["state_abbr"].isin(STATE_NAMES)].copy()
        clean["state_name"] = clean["state_abbr"].map(STATE_NAMES)
        self.frame = clean.sort_values(["state_name", "county_name"]).reset_index(drop=True)

    @classmethod
    def from_csv(cls, path: str | Path) -> "CountyCatalog":
        return cls(pd.read_csv(path, dtype={"fips": str, "state_fips": str, "county_fips": str}))

    def states(self) -> list[tuple[str, str]]:
        values = self.frame[["state_abbr", "state_name"]].drop_duplicates()
        return sorted(values.itertuples(index=False, name=None), key=lambda item: item[1])

    def counties(self, state_abbr: str) -> list[CountyRecord]:
        rows = self.frame[self.frame["state_abbr"] == state_abbr.upper()]
        return [
            CountyRecord(
                fips=str(row.fips),
                state_abbr=str(row.state_abbr),
                state_name=str(row.state_name),
                county_name=str(row.county_name),
                latitude=float(row.latitude),
                longitude=float(row.longitude),
            )
            for row in rows.itertuples(index=False)
        ]

    def find(self, state_abbr: str, county_name: str) -> CountyRecord:
        needle = county_name.casefold().removesuffix(" county").strip()
        for record in self.counties(state_abbr):
            if record.county_name.casefold().removesuffix(" county").strip() == needle:
                return record
        raise LocationError(f"County {county_name!r} was not found in {state_abbr}.")

    def as_location(self, record: CountyRecord) -> Location:
        return Location(
            label=record.label,
            latitude=record.latitude,
            longitude=record.longitude,
            state_abbr=record.state_abbr,
            county_name=record.county_name,
            source="county_catalog",
        )


def geocode_candidates(query: str, *, count: int = 10, session: requests.Session | None = None) -> list[Location]:
    text = query.strip()
    if len(text) < 2:
        raise LocationError("Enter at least two characters for a place or ZIP search.")
    client = session or requests.Session()
    response = client.get(
        GEOCODING_URL,
        params={"name": text, "count": max(1, min(int(count), 25)), "language": "en", "format": "json"},
        timeout=30,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise LocationError(f"Location service error: {response.text[:300]}") from exc
    payload = response.json()
    results = payload.get("results") or []
    locations: list[Location] = []
    seen: set[tuple[float, float]] = set()
    for item in results:
        country_code = str(item.get("country_code") or "").upper()
        if country_code and country_code not in {"US", "PR"}:
            continue
        lat = float(item["latitude"])
        lon = float(item["longitude"])
        marker = (round(lat, 4), round(lon, 4))
        if marker in seen:
            continue
        seen.add(marker)
        pieces = [item.get("name"), item.get("admin2"), item.get("admin1")]
        label = ", ".join(str(piece) for piece in pieces if piece)
        locations.append(
            Location(
                label=label or text,
                latitude=lat,
                longitude=lon,
                timezone=str(item.get("timezone") or "auto"),
                state_abbr=None,
                county_name=str(item.get("admin2")) if item.get("admin2") else None,
                source="open_meteo_geocoding",
            )
        )
    if not locations:
        raise LocationError(f"No U.S. location matches were found for {text!r}.")
    return locations


def destination_point(latitude: float, longitude: float, distance_miles: float, bearing_degrees: float) -> tuple[float, float]:
    angular_distance = float(distance_miles) / EARTH_RADIUS_MILES
    bearing = math.radians(float(bearing_degrees))
    lat1 = math.radians(float(latitude))
    lon1 = math.radians(float(longitude))
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    lon2 = (lon2 + 3 * math.pi) % (2 * math.pi) - math.pi
    return math.degrees(lat2), math.degrees(lon2)


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(value)))


def sample_radius(latitude: float, longitude: float, radius_miles: float, sample_count: int) -> list[SamplePoint]:
    """Create area-balanced points using a golden-angle disk pattern."""
    count = max(1, min(int(sample_count), 49))
    radius = max(0.0, min(float(radius_miles), 250.0))
    points = [SamplePoint("center", float(latitude), float(longitude), 0.0, 0.0)]
    if count == 1 or radius == 0:
        return points
    for index in range(1, count):
        fraction = math.sqrt(index / (count - 1))
        distance = radius * fraction
        bearing = (index * GOLDEN_ANGLE_DEGREES) % 360.0
        lat, lon = destination_point(latitude, longitude, distance, bearing)
        points.append(
            SamplePoint(
                point_id=f"p{index:02d}",
                latitude=round(lat, 6),
                longitude=round(lon, 6),
                distance_miles=round(distance, 3),
                bearing_degrees=round(bearing, 3),
            )
        )
    return points


def center_of_points(points: Iterable[SamplePoint]) -> tuple[float, float]:
    rows = list(points)
    if not rows:
        raise ValueError("At least one point is required.")
    return sum(point.latitude for point in rows) / len(rows), sum(point.longitude for point in rows) / len(rows)
