from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).parents[1]
LEDGER = ROOT / "docs" / "claim_ledger.csv"
SOURCE_DIR = ROOT / "reports" / "1781000867.546870.5c124aaf"

EXPECTED = {
    "claim_text": "S10b run-average 10% template live-time relative to CFD20",
    "current_value": "124.79018394263471",
    "unit": "ns",
    "stat_unc": "",
    "syst_unc": "",
    "total_unc": "",
    "ci_low": "123.33094981246663",
    "ci_high": "126.35875117626817",
    "ci_level": "0.95",
    "ci_method": "run_mean_nonparametric_bootstrap_percentile",
    "bootstrap_unit": "run",
    "n_runs": "14",
    "n_data": "252266",
    "truth_type": "data_measurement",
    "status": "DONE_DATA_ONLY",
    "allowed_status_validated": "NO",
    "source_report": "reports/1781000867.546870.5c124aaf/REPORT.md",
    "source_script": (
        "reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py"
    ),
    "source_data": "reports/1781000867.546870.5c124aaf/result.json",
    "source_manifest": "reports/1781000867.546870.5c124aaf/manifest.json",
    "source_commit": "da9651c56ef6495ce9656d84b69b600daa6d8f86",
    "link_validated": "YES",
    "ci_status": "CI_AVAILABLE_RUN_BOOTSTRAP_METHOD_LIMITATIONS",
    "blocked_by": "BLK-S10B-001",
    "supersedes": "90 ns",
}


def _claim() -> dict[str, str]:
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert len(reader.fieldnames) == 43
        rows = [row for row in reader if row["claim_id"] == "CL-011"]
    assert len(rows) == 1
    return rows[0]


def test_cl011_matches_primary_s10b_contract() -> None:
    row = _claim()
    for field, expected in EXPECTED.items():
        assert row[field] == expected
    notes = row["notes"]
    for phrase in (
        "run-average estimand",
        "14 runs",
        "252266 selected pulses",
        "not a detector-wide universal dead time",
        "MV5 uses the value as an input rather than independently validating it",
        "no statistical/systematic uncertainty decomposition",
    ):
        assert phrase in notes


def test_cl011_counts_and_central_value_reconstruct_from_tracked_summary() -> None:
    result = json.loads((SOURCE_DIR / "result.json").read_text(encoding="utf-8"))
    with (SOURCE_DIR / "heldout_run_summary.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    values = [float(row["traditional_template_live10_ns"]) for row in rows]
    counts = [int(row["n_pulses"]) for row in rows]
    reconstructed = math.fsum(values) / len(values)
    measured = result["traditional"]["tau_eff_live10_ns"]
    assert len(rows) == 14
    assert len({row["heldout_run"] for row in rows}) == 14
    assert sum(counts) == 252266
    assert math.isclose(reconstructed, measured, rel_tol=0.0, abs_tol=2e-14)
    assert result["traditional"]["tau_eff_live10_ci95_ns"] == [
        123.33094981246663,
        126.35875117626817,
    ]
    assert result["git_commit"] == EXPECTED["source_commit"]
