from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from .models import AlertDecision


class AlertError(RuntimeError):
    """Raised when an alert cannot be sent."""


class AlertState:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def should_send(self, key: str, *, cooldown_hours: float, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        previous_text = self.data.get(key)
        if not previous_text:
            return True
        try:
            previous = datetime.fromisoformat(previous_text)
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
        except ValueError:
            return True
        return current - previous >= timedelta(hours=float(cooldown_hours))

    def mark_sent(self, key: str, *, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        self.data[key] = current.astimezone(timezone.utc).isoformat()
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)


class NtfyClient:
    def __init__(
        self,
        *,
        topic: str,
        server: str = "https://ntfy.sh",
        token: str | None = None,
        session: requests.Session | None = None,
    ):
        if not topic.strip():
            raise AlertError("NTFY_TOPIC is empty.")
        self.topic = topic.strip()
        self.server = server.rstrip("/")
        self.token = token
        self.session = session or requests.Session()

    @classmethod
    def from_environment(cls) -> "NtfyClient":
        topic = os.getenv("NTFY_TOPIC", "")
        server = os.getenv("NTFY_SERVER") or "https://ntfy.sh"
        token = os.getenv("NTFY_TOKEN") or None
        return cls(topic=topic, server=server, token=token)

    def publish(self, decision: AlertDecision) -> None:
        payload: dict[str, Any] = {
            "topic": self.topic,
            "title": decision.title,
            "message": decision.message,
            "priority": int(decision.priority),
            "tags": list(decision.tags),
            "markdown": True,
        }
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = self.session.post(
            f"{self.server}/",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise AlertError(f"ntfy returned {response.status_code}: {response.text[:300]}") from exc
