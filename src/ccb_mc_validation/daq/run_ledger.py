"""Machine-readable run ledger helpers (#962)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SCHEMA = "ccb-run-ledger/1"


class RunLedgerError(RuntimeError):
    """Invalid or contradictory run-ledger content."""


def load_run_ledger(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise RunLedgerError(f"run ledger must be a mapping: {path}")
    if payload.get("schema") != SCHEMA:
        raise RunLedgerError(
            f"unsupported run ledger schema {payload.get('schema')!r}; expected {SCHEMA}"
        )
    return payload


def sample_ii_calibration_runs(ledger: dict[str, Any]) -> list[int]:
    sample_ii = ledger.get("samples", {}).get("sample_ii", {})
    runs = [int(r) for r in sample_ii.get("calibration_runs", [])]
    if not runs:
        raise RunLedgerError("sample_ii.calibration_runs missing/empty in run ledger")
    return runs


def assert_no_role_contradiction(ledger: dict[str, Any]) -> None:
    """Fail if the same run is both calibration and independent validation for one study object."""
    for study, roles in (ledger.get("study_roles") or {}).items():
        calib = set(int(x) for x in roles.get("calibration", []))
        heldout = set(int(x) for x in roles.get("independent_validation", []))
        overlap = calib & heldout
        if overlap:
            raise RunLedgerError(
                f"study {study!r} assigns runs {sorted(overlap)} to both "
                "calibration and independent_validation"
            )


def reconcile_sample_ii_calibration(ledger: dict[str, Any]) -> dict[str, Any]:
    """Return the evidence-bound Sample II calibration decision (run 64, not 61)."""
    decision = ledger.get("decisions", {}).get("sample_ii_calibration_run", {})
    if int(decision.get("canonical_run", -1)) != 64:
        raise RunLedgerError(
            "canonical Sample II calibration run must be 64 per newer report evidence"
        )
    if 61 in sample_ii_calibration_runs(ledger):
        raise RunLedgerError("run 61 must not appear in sample_ii calibration_runs")
    return decision
