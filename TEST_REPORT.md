# Test report

Validated on July 22, 2026 with Python 3.13.5 in the artifact build environment.

```text
33 passed, 1 skipped
```

The skipped test is `tests/test_app.py`. It is a Streamlit AppTest smoke test and was skipped only because Streamlit is not installed in the artifact build environment. Streamlit is declared in `requirements.txt`; the test remains enabled in the included GitHub Actions Python 3.11 and 3.12 matrix.

Additional checks completed:

- `python -m compileall -q app.py mushroom_watch scripts tests`
- 80% statement coverage across the `mushroom_watch` package
- deterministic model, geometry, weather-parser, alert, cooldown, observation, repository-link, GitHub/Streamlit deployment, Issue Form, and workflow tests
- Python syntax compilation for the GitHub-first Streamlit changes
- shell syntax checks for GitHub/Streamlit deployment startup and shutdown scripts
- YAML parsing for Issue Forms and configuration files
- Git staging and whitespace validation
- extraction and retesting of the final ZIP

No deterministic unit test calls a live weather, Census, GitHub, Streamlit Cloud, or ntfy service. Network behavior is mocked where applicable.
