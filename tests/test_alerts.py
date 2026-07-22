from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mushroom_watch.alerts import AlertError, AlertState, NtfyClient
from mushroom_watch.models import AlertDecision


class FakeResponse:
    status_code = 200
    text = "ok"

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, data, headers, timeout):
        self.calls.append((url, data, headers, timeout))
        return FakeResponse()


def decision():
    return AlertDecision(
        watch_name="Steuben",
        alert_type="recharge",
        key="recharge:test",
        title="Rain recharge",
        message="At least one inch is forecast.",
        priority=4,
        tags=("rain_cloud", "mushroom"),
    )


def test_cooldown_state_round_trip(tmp_path):
    state = AlertState(tmp_path / "state.json")
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    assert state.should_send("x", cooldown_hours=72, now=now)
    state.mark_sent("x", now=now)
    restored = AlertState(tmp_path / "state.json")
    assert not restored.should_send("x", cooldown_hours=72, now=now + timedelta(hours=71))
    assert restored.should_send("x", cooldown_hours=72, now=now + timedelta(hours=72))


def test_ntfy_json_payload_and_auth_header():
    session = FakeSession()
    client = NtfyClient(topic="long-private-topic", token="secret", session=session)
    client.publish(decision())
    url, raw, headers, timeout = session.calls[0]
    payload = json.loads(raw)
    assert url == "https://ntfy.sh/"
    assert payload["topic"] == "long-private-topic"
    assert payload["markdown"] is True
    assert payload["tags"] == ["rain_cloud", "mushroom"]
    assert headers["Authorization"] == "Bearer secret"
    assert timeout == 30


def test_environment_uses_default_server_for_empty_optional_secret(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "long-private-topic")
    monkeypatch.setenv("NTFY_SERVER", "")
    client = NtfyClient.from_environment()
    assert client.server == "https://ntfy.sh"


def test_empty_ntfy_topic_is_rejected():
    with pytest.raises(AlertError):
        NtfyClient(topic=" ")
