"""Filesystem client — reads workflows from a local checkout.

Port of lib/local_client.rb (GitHub Actions surface only; the GitLab/
Bitbucket platform configs the Ruby client also returned are out of scope
for the maintainer Guardian, which guards a single GitHub repo). The
Guardian scans the repo it lives in, so the local client is the only one
the port ships.
"""

from __future__ import annotations

import glob
import os
from typing import Any

import yaml


class LocalClient:
    """Reads `.github/workflows/*.{yml,yaml}` + dependabot config from a path."""

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        self.workflows_dir = os.path.join(self.path, ".github", "workflows")

    def fetch_workflows(self, _repo: Any = None) -> list[dict[str, str]]:
        """Return [{filename, content}] for every workflow file, sorted by name."""
        workflows: list[dict[str, str]] = []
        if not os.path.isdir(self.workflows_dir):
            return workflows
        files = sorted(glob.glob(os.path.join(self.workflows_dir, "*.yml")) + glob.glob(os.path.join(self.workflows_dir, "*.yaml")))
        for f in files:
            with open(f, encoding="utf-8") as fh:
                content = fh.read()
            workflows.append({"filename": os.path.basename(f), "content": content})
        return workflows

    def file_exists(self, _repo: Any, path: str) -> bool:
        """True iff `path` (repo-relative) exists in the checkout."""
        return os.path.exists(os.path.join(self.path, path))

    def fetch_dependabot_config(self, _repo: Any = None) -> dict[str, Any] | None:
        """Parsed `.github/dependabot.yml` (or .yaml), or None when absent/bad."""
        path = os.path.join(self.path, ".github", "dependabot.yml")
        if not os.path.exists(path):
            path = os.path.join(self.path, ".github", "dependabot.yaml")
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh.read())
            return data if isinstance(data, dict) else None
        except (OSError, yaml.YAMLError):
            return None
