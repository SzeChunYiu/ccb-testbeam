"""Capture runtime environment metadata for reproducibility."""

from __future__ import annotations

import platform
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any


def _git_head() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def capture_environment(*, extra_packages: tuple[str, ...] = ("numpy", "pandas", "uproot")) -> dict[str, Any]:
    """Snapshot Python, platform, git commit, and package versions."""
    packages = {name: _package_version(name) for name in extra_packages}
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git_commit": _git_head(),
        "packages": {k: v for k, v in packages.items() if v is not None},
    }
