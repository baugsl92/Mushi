from __future__ import annotations

from contextlib import closing
import io
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

OBSERVATION_COLUMNS = [
    "observation_id", "observed_at", "location_label", "latitude", "longitude",
    "guild", "taxon", "found", "abundance", "habitat", "substrate",
    "host_tree", "notes", "photo_url", "modeled_score", "confidence_label", "created_at",
]


def _clean_value(value: Any) -> Any:
    """Turn pandas missing scalars into None before writing to SQLite."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


class ObservationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY,
                    observed_at TEXT NOT NULL,
                    location_label TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    guild TEXT NOT NULL,
                    taxon TEXT,
                    found INTEGER NOT NULL,
                    abundance TEXT,
                    habitat TEXT,
                    substrate TEXT,
                    host_tree TEXT,
                    notes TEXT,
                    photo_url TEXT,
                    modeled_score REAL,
                    confidence_label TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def add(self, observation: dict[str, Any]) -> str:
        observation = {key: _clean_value(value) for key, value in observation.items()}
        observation_id = str(observation.get("observation_id") or uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "observation_id": observation_id,
            "observed_at": str(observation["observed_at"]),
            "location_label": str(observation["location_label"]),
            "latitude": observation.get("latitude"),
            "longitude": observation.get("longitude"),
            "guild": str(observation["guild"]),
            "taxon": observation.get("taxon"),
            "found": 1 if bool(observation.get("found")) else 0,
            "abundance": observation.get("abundance"),
            "habitat": observation.get("habitat"),
            "substrate": observation.get("substrate"),
            "host_tree": observation.get("host_tree"),
            "notes": observation.get("notes"),
            "photo_url": observation.get("photo_url"),
            "modeled_score": observation.get("modeled_score"),
            "confidence_label": observation.get("confidence_label"),
            "created_at": str(observation.get("created_at") or now),
        }
        columns = list(row)
        placeholders = ",".join("?" for _ in columns)
        with closing(self._connect()) as connection:
            connection.execute(
                f"INSERT OR REPLACE INTO observations ({','.join(columns)}) VALUES ({placeholders})",
                [row[column] for column in columns],
            )
            connection.commit()
        return observation_id

    def list(self, *, limit: int | None = None) -> pd.DataFrame:
        query = "SELECT * FROM observations ORDER BY observed_at DESC, created_at DESC"
        params: tuple[Any, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (int(limit),)
        with closing(self._connect()) as connection:
            frame = pd.read_sql_query(query, connection, params=params)
        if not frame.empty:
            frame["found"] = frame["found"].astype(bool)
        return frame.reindex(columns=OBSERVATION_COLUMNS)

    def export_csv(self) -> bytes:
        return self.list().to_csv(index=False).encode("utf-8")

    def import_csv(self, content: bytes | str) -> int:
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
        frame = pd.read_csv(io.StringIO(text))
        required = {"observed_at", "location_label", "guild", "found"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Observation CSV is missing: {', '.join(sorted(missing))}")
        count = 0
        for record in frame.to_dict(orient="records"):
            found_value = record.get("found")
            if isinstance(found_value, str):
                record["found"] = found_value.strip().lower() in {"1", "true", "yes", "y", "found"}
            self.add(record)
            count += 1
        return count
