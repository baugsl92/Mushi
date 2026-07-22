# Contributing

Use GitHub Codespaces for the simplest contributor environment. The `.devcontainer` configuration installs all development dependencies and starts Streamlit automatically.

1. Create a branch in GitHub or Codespaces.
2. Make the smallest focused change possible.
3. Run `pytest -q`.
4. Commit and push the branch.
5. Open a pull request and allow the **Tests** workflow to finish.

Model changes belong in `config/guilds.yaml` or the scoring modules and should include tests. Do not alter several biological thresholds at once without documenting the field evidence and expected calibration effect.

Never commit ntfy topics, tokens, `.streamlit/secrets.toml`, local SQLite files, or alert-state files.
