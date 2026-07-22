from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .geo import CountyCatalog, geocode_candidates
from .models import Location


class WatchConfigError(ValueError):
    """Raised when watch_config.yaml is invalid."""


def load_watch_config(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    watches = payload.get("watches")
    if not isinstance(watches, list) or not watches:
        raise WatchConfigError("The configuration must contain a non-empty 'watches' list.")
    cleaned = []
    for index, watch in enumerate(watches, start=1):
        if not isinstance(watch, dict):
            raise WatchConfigError(f"Watch {index} must be a mapping.")
        for required in ["name", "location", "guilds"]:
            if required not in watch:
                raise WatchConfigError(f"Watch {index} is missing {required!r}.")
        cleaned.append(watch)
    return cleaned


def resolve_watch_location(location_cfg: dict[str, Any], county_catalog: CountyCatalog) -> Location:
    mode = str(location_cfg.get("mode", "county"))
    if mode == "county":
        state = str(location_cfg.get("state", "")).upper()
        county = str(location_cfg.get("county", ""))
        return county_catalog.as_location(county_catalog.find(state, county))
    if mode == "query":
        query = str(location_cfg.get("query", ""))
        return geocode_candidates(query, count=5)[0]
    if mode == "coordinates":
        return Location(
            label=str(location_cfg.get("label") or "Custom coordinates"),
            latitude=float(location_cfg["latitude"]),
            longitude=float(location_cfg["longitude"]),
            timezone=str(location_cfg.get("timezone") or "auto"),
            source="coordinates",
        )
    raise WatchConfigError(f"Unknown location mode: {mode}")


def dump_watch_config(watch: dict[str, Any]) -> str:
    return yaml.safe_dump({"watches": [watch]}, sort_keys=False, allow_unicode=True)
