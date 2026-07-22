from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Mapping
from urllib.parse import urlencode

_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def normalize_repository_slug(value: str | None) -> str | None:
    """Return an owner/repository slug when *value* is recognizable."""
    if not value:
        return None
    text = value.strip()
    if text.startswith("git@github.com:"):
        text = text.removeprefix("git@github.com:")
    elif text.startswith("ssh://git@github.com/"):
        text = text.removeprefix("ssh://git@github.com/")
    elif text.startswith("https://github.com/"):
        text = text.removeprefix("https://github.com/")
    elif text.startswith("http://github.com/"):
        text = text.removeprefix("http://github.com/")
    text = text.rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    return text if _REPOSITORY_RE.fullmatch(text) else None


def detect_repository_slug(root: str | Path | None = None) -> str | None:
    """Detect the GitHub owner/repository from environment variables or git."""
    for name in ("MUSHROOM_WATCH_REPOSITORY", "GITHUB_REPOSITORY"):
        detected = normalize_repository_slug(os.getenv(name))
        if detected:
            return detected

    cwd = Path(root or Path.cwd())
    try:
        completed = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return normalize_repository_slug(completed.stdout)


def issue_form_url(
    repository_slug: str,
    *,
    template: str = "field-observation.yml",
    values: Mapping[str, object] | None = None,
) -> str:
    slug = normalize_repository_slug(repository_slug)
    if not slug:
        raise ValueError("Repository must use the owner/repository format.")
    params: dict[str, str] = {"template": template}
    for key, value in (values or {}).items():
        if value is not None and str(value).strip():
            params[str(key)] = str(value)
    return f"https://github.com/{slug}/issues/new?{urlencode(params)}"


def observation_issues_url(repository_slug: str) -> str:
    slug = normalize_repository_slug(repository_slug)
    if not slug:
        raise ValueError("Repository must use the owner/repository format.")
    return f"https://github.com/{slug}/issues?q=is%3Aissue+label%3Afield-observation"


def edit_file_url(repository_slug: str, path: str, *, branch: str = "main") -> str:
    slug = normalize_repository_slug(repository_slug)
    if not slug:
        raise ValueError("Repository must use the owner/repository format.")
    clean_path = path.lstrip("/")
    return f"https://github.com/{slug}/edit/{branch}/{clean_path}"
