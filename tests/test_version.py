"""Tests for release metadata consistency."""

import json
import tomllib
from pathlib import Path

from custom_components.sparkyfitness.const import INTEGRATION_VERSION

ROOT = Path(__file__).parents[1]


def test_release_versions_are_synchronized() -> None:
    """Manifest, client identity, and project metadata use one release version."""

    manifest = json.loads(
        (ROOT / "custom_components" / "sparkyfitness" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["version"] == INTEGRATION_VERSION
    assert project["project"]["version"] == INTEGRATION_VERSION
