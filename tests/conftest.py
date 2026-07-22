from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mushroom_watch.profiles import load_profiles
from mushroom_watch.weather import synthetic_weather_frame

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def profiles():
    return load_profiles(ROOT / "config" / "guilds.yaml")


@pytest.fixture
def weather_frame() -> pd.DataFrame:
    return synthetic_weather_frame(days=45, start="2026-04-01")
