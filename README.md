# Mushroom Watch 2.0

Mushroom Watch is a GitHub-hosted Streamlit project for estimating weather compatibility for mushroom fruiting. GitHub stores the project and runs scheduled alerts; Streamlit Community Cloud hosts the dashboard.

## Begin here

Open **[START_HERE.md](START_HERE.md)**. The setup is:

1. Upload this folder's contents to a new GitHub repository.
2. Connect that repository to Streamlit Community Cloud.
3. Select `app.py` as the Streamlit entrypoint.

No local Python installation or Codespace is required.

## Models included

- Morels
- Ectomycorrhizal mushrooms
- Wood-decay mushrooms
- Soil and litter saprotrophs

The model includes 30-day antecedent precipitation, normalized soil moisture, a multiplicative moisture limiter, temperature trends, degree-days, atmospheric dry-down, evidence-confidence labels, and rolling 8–72-hour recharge alerts for at least 1 inch of forecast precipitation.

## Repository map

```text
.github/ISSUE_TEMPLATE/     Permanent field-observation form
.github/workflows/          Tests and scheduled ntfy alerts
.streamlit/                 Streamlit appearance and optional secrets example
app.py                      Streamlit dashboard entrypoint
config/guilds.yaml          Guild scoring profiles
data/county_centroids.csv   Offline U.S. county selector
mushroom_watch/             Tested application and scoring code
scripts/check_alerts.py     GitHub Actions alert entrypoint
watch_config.yaml           Scheduled-watch configuration
```

## GitHub Actions alerts

The dashboard does not need ntfy. For optional alerts, add `NTFY_TOPIC` under **GitHub repository Settings → Secrets and variables → Actions**, then manually run **Mushroom alerts** with Dry run enabled.

## Updating the app

Edit or upload a changed file in GitHub and commit it. Streamlit Community Cloud redeploys from the repository automatically.

## Testing

GitHub Actions runs the tests after pushes and pull requests. The workflow uses Python 3.11 and 3.12.

## Scientific scope and safety

The guild profiles are transparent, field-informed heuristics, not peer-reviewed fruiting equations. Weather compatibility does not confirm that mushrooms are present, correctly identified, or edible. Never eat a wild mushroom based on this app or a photograph. See **[MODEL.md](MODEL.md)** for equations, assumptions, and calibration guidance.

## License

MIT. See [LICENSE](LICENSE).
