# Data directory

- `county_centroids.csv` is the bundled offline county/equivalent selector.
- `observations.sqlite3` is created when field observations are saved locally.
- `alert_state.json` is created by the scheduled checker for cooldown tracking.

The two runtime files are ignored by Git. Refresh county centroids from the official 2025 U.S. Census Gazetteer with:

```bash
python scripts/update_counties.py
```
