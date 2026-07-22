from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="Streamlit is installed by requirements-dev.txt and GitHub Actions.")
from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_without_network_calls():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert not app.exception
    assert any("Mushroom Watch 2.0" in title.value for title in app.title)
    assert any("Analyze conditions" in button.label for button in app.button)
