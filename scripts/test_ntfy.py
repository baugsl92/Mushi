from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mushroom_watch.alerts import NtfyClient
from mushroom_watch.models import AlertDecision


def main() -> None:
    client = NtfyClient.from_environment()
    client.publish(
        AlertDecision(
            watch_name="Test",
            alert_type="test",
            key="test",
            title="🍄 Mushroom Watch test",
            message="Your ntfy connection is working.",
            priority=3,
            tags=("white_check_mark", "mushroom"),
        )
    )
    print("Test notification sent.")


if __name__ == "__main__":
    main()
