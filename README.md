# Mushroom Watch 2.0 — GitHub Edition

Mushroom Watch 2.0 is a repository-first Streamlit project for estimating **weather compatibility for mushroom fruiting**. You can run the dashboard in a browser with GitHub Codespaces, schedule ntfy checks with GitHub Actions, and store field observations as durable GitHub Issues. No local Python installation is required.

It models four ecological guilds separately:

- Morels
- Ectomycorrhizal mushrooms, including chanterelles, boletes, russulas, and milkcaps
- Wood-decay mushrooms, including oysters, chicken of the woods, maitake, and Hericium
- Soil and litter saprotrophs, including Agaricus, parasols, and puffballs

It does **not** confirm presence, identify a specimen, determine edibility, or replace field expertise.

## Fastest setup: everything from GitHub

### 1. Create the repository

1. Create a new empty GitHub repository.
2. Upload all project files and folders to the repository root.
3. Be sure the hidden folders `.github`, `.devcontainer`, and `.streamlit` are included.
4. Commit the upload to the `main` branch.

### 2. Open Mushroom Watch in Codespaces

1. On the repository page, click **Code**.
2. Open the **Codespaces** tab.
3. Click **Create codespace on main**.
4. The repository automatically installs dependencies and starts Streamlit.
5. When GitHub reports that port **8501** is available, click **Open in Browser**.

The forwarded app port is private by default. Reopen the same Codespace later from **Code → Codespaces**. See [GITHUB_ONLY_SETUP.md](GITHUB_ONLY_SETUP.md) for screenshots-level instructions and troubleshooting.

### 3. Configure scheduled phone alerts

1. Edit and commit `watch_config.yaml` with the location and guilds you want monitored.
2. Open **Settings → Secrets and variables → Actions**.
3. Add the required repository secret `NTFY_TOPIC`.
4. Optionally add `NTFY_SERVER` and `NTFY_TOKEN`.
5. Open **Actions → Mushroom alerts → Run workflow**.
6. Keep **Dry run** enabled for the first run.
7. Run it again with Dry run disabled to test an actual notification.

The scheduled workflow checks each day at **7:05 a.m. America/Detroit**. GitHub Actions performs the scheduled work even when your Codespace and dashboard are closed.

### 4. Log field observations permanently

Inside the dashboard, open **Field observations** and click **Log an observation in GitHub**. The Issue Form stores the observation in the repository. A companion workflow automatically applies the `field-observation` label.

Record unsuccessful searches too. Negative observations are important for detecting false positives and calibrating the model. Avoid posting sensitive exact mushroom locations; use a county, park, broad site, or rounded coordinates.

## Optional permanent dashboard URL

Codespaces is ideal for your own browser sessions but can stop when idle. For a permanent web address, deploy `app.py` from the same repository using Streamlit Community Cloud. Scheduled alerts still run through GitHub Actions, and observations still persist in GitHub Issues.

## What is included

- Thirty-day antecedent precipitation and a recency-weighted precipitation index
- Soil moisture normalized against the location's recent modeled range
- Moisture as a **limiting multiplier**, so favorable temperature cannot erase drought
- Seven-day temperature trends and guild-specific degree-days
- Atmospheric dry-down from vapor-pressure deficit, FAO ET₀, wind, and humidity
- Separate morel, ectomycorrhizal, wood-decay, and soil/litter saprotroph models
- Evidence-confidence labels based on data completeness, history, forecast lead, sample count, and spatial agreement
- Rolling 8–72-hour recharge detection for at least 1.00 inch of forecast rain
- State/county, city/ZIP, coordinate, radius, and area-balanced sampling controls
- GitHub Issue Form field logging plus an optional temporary SQLite scratch log
- ntfy notifications with cooldown protection
- Automatic Codespaces setup and Streamlit startup
- GitHub Actions for tests, observation labeling, and scheduled alerts
- A deterministic mocked test suite that does not require live API calls

## Scientific model in plain language

Every guild receives a transparent base score from season, air temperature, modeled soil temperature, temperature trend, accumulated degree-days, overnight humidity, and guild-specific terms. Moisture then limits the result:

```text
final score = base score × moisture multiplier

moisture multiplier = min(soil-moisture gate, precipitation gate)
                      × atmospheric dry-down multiplier
```

The precipitation gate combines the 30-day recency-weighted antecedent index with rain from the latest 72 hours. The soil gate compares current modeled soil moisture with its rolling local 10th-to-90th-percentile range. Wood-decay fungi receive partial relief from the mineral-soil gate because soil moisture is only an imperfect proxy for moisture held in wood.

These profiles are **field-informed starting heuristics**, not peer-reviewed fruiting equations. See [MODEL.md](MODEL.md) for the full equations, assumptions, and calibration guidance.

## Repository map

```text
.devcontainer/                 Codespaces setup and automatic Streamlit startup
.github/ISSUE_TEMPLATE/        Permanent field-observation form
.github/workflows/             Tests, alerts, and observation labeling
app.py                         Streamlit dashboard
config/guilds.yaml             Four guild scoring profiles
data/county_centroids.csv      Offline U.S. county selector
mushroom_watch/                Tested application and scientific model code
scripts/check_alerts.py        Scheduled alert entrypoint
watch_config.yaml              Committed scheduled-watch configuration
```

## Test the repository

Tests run automatically after pushes and pull requests. You can also open **Actions → Tests → Run workflow**.

Inside Codespaces, run:

```bash
pytest -q
```

## Change alert settings

Use the dashboard's **Alert configuration** tab to generate YAML. Then open `watch_config.yaml` in GitHub or Codespaces, replace its contents, and commit the change. Scheduled Actions always use the committed version.

## Restart the Codespaces dashboard

```bash
bash .devcontainer/stop-app.sh
bash .devcontainer/start-app.sh
```

View the server log:

```bash
tail -f .codespaces/streamlit.log
```

## Optional local setup

The project still supports Python 3.11 or 3.12 locally:

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
streamlit run app.py
```

Local setup is not required for the GitHub workflow.

## Data sources and limits

Weather comes from Open-Meteo's gridded forecast and historical model data. A localized storm, ravine, canopy, slope aspect, host tree, substrate, irrigation, soil texture, disturbance history, and established mycelium can produce field conditions unlike the modeled grid.

The county selector is a static U.S. county/equivalent centroid snapshot. Refresh it with `python scripts/update_counties.py` when a newer official Census Gazetteer file is needed.

## Safety

Never eat a wild mushroom based on this app, a photograph, an automated identification, bruising color, or weather conditions. Confirm the entire specimen using appropriate taxonomic characters and qualified local expertise. Some deadly mushrooms resemble edible species.

## Technical references

- GitHub Codespaces and dev containers: https://docs.github.com/codespaces
- GitHub Actions workflow syntax: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Issue Forms: https://docs.github.com/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Streamlit Community Cloud: https://docs.streamlit.io/deploy/streamlit-community-cloud
- Open-Meteo Forecast API: https://open-meteo.com/en/docs
- ntfy publishing: https://docs.ntfy.sh/publish/

## License

MIT. See [LICENSE](LICENSE).
