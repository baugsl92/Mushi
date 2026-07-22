# GitHub-only setup

This edition is designed so you do not need to install Python on your computer.

## What runs where

- **Dashboard:** GitHub Codespaces starts Streamlit automatically and opens port 8501 in your browser.
- **Scheduled checks:** GitHub Actions runs `scripts/check_alerts.py` each morning.
- **Field observations:** GitHub Issue Forms store each observation permanently in the repository.
- **Tests:** GitHub Actions runs the complete test suite after each push or pull request.
- **Optional always-available public dashboard:** Streamlit Community Cloud deploys directly from the same GitHub repository.

## One-time repository setup

1. Create a new empty GitHub repository.
2. Upload every file and folder from this project, including the hidden `.github`, `.devcontainer`, and `.streamlit` folders.
3. Commit the upload to the `main` branch.
4. On the repository page, click **Code → Codespaces → Create codespace on main**.
5. Wait for the browser workspace to open. Dependencies install automatically, Streamlit starts automatically, and GitHub forwards port 8501.
6. When the **Mushroom Watch** port notification appears, click **Open in Browser**. The port is private by default.

After the first setup, reopen the application from **Code → Codespaces** and select the existing codespace. You do not need to repeat installation.

## Configure scheduled ntfy alerts

1. Edit `watch_config.yaml` in GitHub or Codespaces and commit the change.
2. Open **Settings → Secrets and variables → Actions**.
3. Add the required secret `NTFY_TOPIC`.
4. Add `NTFY_SERVER` and `NTFY_TOKEN` only when needed.
5. Open **Actions → Mushroom alerts → Run workflow**.
6. Leave **Dry run** checked for the first test. Run it again with Dry run unchecked to test a real notification.

Scheduled runs use the committed `watch_config.yaml`. The included schedule is 7:05 a.m. in `America/Detroit`.

## Log field observations

Open Mushroom Watch and select **Field observations → Log an observation in GitHub**. The issue form records positive and negative searches, habitat, substrate, host trees, score, confidence, and notes. Submitting the form creates a durable issue labeled `field-observation`.

Do not publish sensitive exact mushroom locations. A county, park, or rounded coordinate is usually enough for model calibration.

## Optional permanent dashboard URL

Codespaces is intended for your own interactive sessions and stops when idle. For a permanent app URL:

1. Sign in to Streamlit Community Cloud with GitHub.
2. Choose **Create app** and select this repository.
3. Use `app.py` as the entrypoint.
4. Deploy.

The scheduled alerts still run in GitHub Actions. Field observations still go to GitHub Issues, so they are not lost when Streamlit restarts.

## Updating the project

Edit files in Codespaces or GitHub's web editor, commit to `main`, and GitHub Actions will test the change. Restart the Streamlit process when Python code changes do not appear:

```bash
bash .devcontainer/stop-app.sh
bash .devcontainer/start-app.sh
```

View the server log with:

```bash
tail -f .codespaces/streamlit.log
```
