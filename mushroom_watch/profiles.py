from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ProfileError(ValueError):
    """Raised when a guild profile file is invalid."""


def load_profiles(path: str | Path) -> dict[str, dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    guilds = payload.get("guilds", payload)
    if not isinstance(guilds, dict) or not guilds:
        raise ProfileError("No guild profiles were found.")
    required = {"display_name", "model_type", "moisture", "temperature", "weights"}
    cleaned: dict[str, dict[str, Any]] = {}
    for key, value in guilds.items():
        if not isinstance(value, dict):
            raise ProfileError(f"Profile {key!r} must be a mapping.")
        missing = sorted(required - set(value))
        if missing:
            raise ProfileError(f"Profile {key!r} is missing: {', '.join(missing)}")
        weights = value.get("weights", {})
        total = sum(float(item) for item in weights.values())
        if abs(total - 100.0) > 0.01:
            raise ProfileError(f"Profile {key!r} weights must total 100, not {total}.")
        cleaned[str(key)] = deepcopy(value)
    return cleaned
