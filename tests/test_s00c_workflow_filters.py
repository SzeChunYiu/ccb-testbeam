"""Regression checks for the self-hosted S00c selector-count workflow scope."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/s00c-selector-count-regression.yml"


def _workflow() -> dict:
    # BaseLoader avoids YAML 1.1 coercion of the GitHub Actions key ``on`` to bool.
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_s00c_self_hosted_guard_is_path_scoped() -> None:
    workflow = _workflow()

    triggers = workflow["on"]
    pull_paths = triggers["pull_request"]["paths"]
    push_paths = triggers["push"]["paths"]

    required = {
        ".github/workflows/s00c-selector-count-regression.yml",
        "configs/s00d_1781028640_1234_005956da_ci_premerge.json",
        "scripts/s00c*.py",
        "scripts/s00d_1781028640_1234_005956da_ci_premerge.py",
        "DATA.md",
    }
    assert required.issubset(set(pull_paths))
    assert pull_paths == push_paths


def test_s00c_self_hosted_guard_does_not_run_for_broad_report_only_changes() -> None:
    workflow = _workflow()
    pull_paths = workflow["on"]["pull_request"]["paths"]

    assert "docs/**" not in pull_paths
    assert "reports/**" not in pull_paths
    assert "wiki/**" not in pull_paths
    assert "publication/**" not in pull_paths
    assert "docs/mc_validation/LUNARC_PRODUCTION_STATUS.md" not in pull_paths
