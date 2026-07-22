from __future__ import annotations

from pathlib import Path

import pytest

from mushroom_watch.geo import CountyCatalog, LocationError, haversine_miles, sample_radius

ROOT = Path(__file__).resolve().parents[1]


def test_county_catalog_finds_steuben():
    catalog = CountyCatalog.from_csv(ROOT / "data" / "county_centroids.csv")
    record = catalog.find("IN", "Steuben County")
    assert record.state_abbr == "IN"
    assert record.county_name == "Steuben"
    assert 41.0 < record.latitude < 42.5
    assert -86.0 < record.longitude < -84.0
    assert "Indiana" in record.label


def test_unknown_county_raises():
    catalog = CountyCatalog.from_csv(ROOT / "data" / "county_centroids.csv")
    with pytest.raises(LocationError):
        catalog.find("IN", "Not A County")


def test_radius_points_are_area_distributed_and_bounded():
    points = sample_radius(41.63, -85.00, radius_miles=50, sample_count=17)
    assert len(points) == 17
    assert points[0].point_id == "center"
    distances = [haversine_miles(41.63, -85.00, point.latitude, point.longitude) for point in points]
    assert distances[0] == pytest.approx(0.0)
    assert max(distances) <= 50.05
    assert len({round(point.bearing_degrees, 1) for point in points[1:]}) == 16
    assert any(15 < distance < 35 for distance in distances)


def test_radius_sampling_caps_input():
    assert len(sample_radius(0, 0, 500, 100)) == 49
    assert max(point.distance_miles for point in sample_radius(0, 0, 500, 49)) == pytest.approx(250)
