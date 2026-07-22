from __future__ import annotations

from mushroom_watch.repository import (
    edit_file_url,
    issue_form_url,
    normalize_repository_slug,
    observation_issues_url,
)


def test_normalize_repository_slug_supports_common_remote_formats():
    assert normalize_repository_slug("owner/repo") == "owner/repo"
    assert normalize_repository_slug("https://github.com/owner/repo.git") == "owner/repo"
    assert normalize_repository_slug("git@github.com:owner/repo.git") == "owner/repo"
    assert normalize_repository_slug("not a repo") is None


def test_repository_urls_are_safe_and_prefilled():
    form = issue_form_url("owner/repo", values={"location": "Steuben County, Indiana", "score": 72})
    assert form.startswith("https://github.com/owner/repo/issues/new?")
    assert "template=field-observation.yml" in form
    assert "location=Steuben+County%2C+Indiana" in form
    assert observation_issues_url("owner/repo").endswith("label%3Afield-observation")
    assert edit_file_url("owner/repo", "/watch_config.yaml") == "https://github.com/owner/repo/edit/main/watch_config.yaml"
