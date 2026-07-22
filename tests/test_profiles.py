from __future__ import annotations

from pathlib import Path

import pytest

from mushroom_watch.profiles import ProfileError, load_profiles


def test_four_required_guilds_are_present(profiles):
    assert set(profiles) == {"morel", "ectomycorrhizal", "wood_decay", "soil_saprotroph"}
    assert {profile["model_type"] for profile in profiles.values()} == set(profiles)


def test_each_base_score_totals_one_hundred(profiles):
    for profile in profiles.values():
        assert sum(profile["weights"].values()) == pytest.approx(100.0)
        assert len(profile["soil_layer_weights"]) == 4
        assert profile["temperature"]["gdd_window_days"] <= 30


def test_invalid_weights_are_rejected(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
guilds:
  bad:
    display_name: Bad
    model_type: bad
    moisture: {}
    temperature: {}
    weights: {season: 99}
""",
        encoding="utf-8",
    )
    with pytest.raises(ProfileError, match="weights must total 100"):
        load_profiles(path)
