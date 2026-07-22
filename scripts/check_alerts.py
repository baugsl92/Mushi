from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mushroom_watch.alerts import AlertState, NtfyClient
from mushroom_watch.config import load_watch_config
from mushroom_watch.geo import CountyCatalog
from mushroom_watch.monitor import fruiting_decisions, recharge_decisions, run_watch_analysis
from mushroom_watch.profiles import load_profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Mushroom Watch conditions and send ntfy alerts.")
    parser.add_argument("--config", default=str(ROOT / "watch_config.yaml"))
    parser.add_argument("--dry-run", action="store_true", help="Print alerts without sending them.")
    parser.add_argument("--ignore-cooldown", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profiles = load_profiles(ROOT / "config" / "guilds.yaml")
    catalog = CountyCatalog.from_csv(ROOT / "data" / "county_centroids.csv")
    watches = load_watch_config(args.config)
    state = AlertState(ROOT / "data" / "alert_state.json")
    client = None if args.dry_run else NtfyClient.from_environment()
    sent = 0
    for watch in watches:
        print(f"Checking {watch['name']}…")
        analysis = run_watch_analysis(watch, county_catalog=catalog, profiles=profiles)
        decisions = fruiting_decisions(watch, analysis, profiles) + recharge_decisions(watch, analysis)
        cooldown = float(watch.get("cooldown_hours", 72))
        if not decisions:
            print("  No alert conditions met.")
            continue
        for decision in decisions:
            if not args.ignore_cooldown and not state.should_send(decision.key, cooldown_hours=cooldown):
                print(f"  Cooldown active: {decision.title}")
                continue
            print(f"  {decision.title}: {decision.message.replace(chr(10), ' ')}")
            if args.dry_run:
                continue
            assert client is not None
            client.publish(decision)
            state.mark_sent(decision.key)
            sent += 1
    print(f"Completed. Sent {sent} alert(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
