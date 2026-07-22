from __future__ import annotations

import pandas as pd

from mushroom_watch.observations import ObservationStore


def observation(**overrides):
    row = {
        "observed_at": "2026-05-01",
        "location_label": "Steuben County, Indiana",
        "latitude": 41.63,
        "longitude": -85.0,
        "guild": "morel",
        "taxon": "Morchella sp.",
        "found": True,
        "abundance": "Few",
    }
    row.update(overrides)
    return row


def test_add_list_export_and_import(tmp_path):
    store = ObservationStore(tmp_path / "observations.sqlite3")
    first_id = store.add(observation())
    frame = store.list()
    assert len(frame) == 1
    assert frame.loc[0, "observation_id"] == first_id
    assert bool(frame.loc[0, "found"]) is True

    exported = store.export_csv()
    other = ObservationStore(tmp_path / "other.sqlite3")
    assert other.import_csv(exported) == 1
    assert len(other.list()) == 1


def test_import_missing_id_and_nan_generates_real_uuid(tmp_path):
    store = ObservationStore(tmp_path / "observations.sqlite3")
    csv_text = "observed_at,location_label,guild,found,observation_id,notes\n2026-05-02,Test Woods,morel,false,,\n"
    store.import_csv(csv_text)
    frame = store.list()
    assert len(frame.loc[0, "observation_id"]) > 20
    assert frame.loc[0, "observation_id"].lower() != "nan"
    assert bool(frame.loc[0, "found"]) is False
