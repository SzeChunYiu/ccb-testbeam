"""Shared helpers for MC validation notebooks."""

from __future__ import annotations

import json
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_dir(run_id: str) -> Path:
    return repo_root() / "reports/mc_validation/runs" / run_id


def load_run_state(run_id: str) -> dict:
    path = run_dir(run_id) / "RUN_STATE.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_study_result(run_id: str, study: str) -> dict:
    path = run_dir(run_id) / study / "study_result.json"
    if not path.is_file():
        return {"status": "NOT_RUN", "metrics": {}}
    return json.loads(path.read_text(encoding="utf-8"))
