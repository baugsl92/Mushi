from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_deployment_files_are_present():
    assert (ROOT / "app.py").is_file()
    assert (ROOT / "requirements.txt").is_file()
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "headless = true" in config
    setup = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
    assert "GitHub first, then Streamlit" in setup
    assert "app.py" in setup


def test_field_observation_issue_form_contains_calibration_fields():
    payload = yaml.safe_load(
        (ROOT / ".github" / "ISSUE_TEMPLATE" / "field-observation.yml").read_text(encoding="utf-8")
    )
    field_ids = {item.get("id") for item in payload["body"] if isinstance(item, dict)}
    assert {"observed_at", "location", "guild", "found", "abundance", "modeled_score"} <= field_ids
    assert payload["title"].startswith("[Observation]:")


def test_alert_workflow_has_manual_dry_run_and_detroit_schedule():
    text = (ROOT / ".github" / "workflows" / "mushroom-alerts.yml").read_text(encoding="utf-8")
    assert "dry_run:" in text
    assert 'timezone: "America/Detroit"' in text
    assert "--dry-run" in text
    assert "NTFY_TOPIC" in text
