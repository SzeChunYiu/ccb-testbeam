from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import math
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "audit_p07e_saturation_claim.py"
SPEC = importlib.util.spec_from_file_location("audit_p07e", MODULE_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def source_payload() -> tuple[str, dict, dict]:
    report = (
        "# P07e\n\n"
        "Raw B-stack ROOT was read directly; no Monte Carlo was used.\n"
        "Split: leave-one-run-out by run.\n"
        "The duplicate readout therefore does not support applying the ratio-transfer correction.\n"
    )
    result = {
        "study": "P07e",
        "ticket_id": "1781018174.2030.05ac1ce2",
        "summary": [
            {
                "method": "ml_ratio_transfer",
                "n": 183132,
                "charge_res68_abs_frac": 0.1763577793605039,
                "run_block_charge_res68_abs_frac_ci95": [
                    0.17304334869529975,
                    0.18060166173702746,
                ],
            },
            {
                "method": "observed_raw",
                "n": 183132,
                "charge_res68_abs_frac": 0.12079374117700271,
                "run_block_charge_res68_abs_frac_ci95": [
                    0.11700387021774719,
                    0.12536373643016782,
                ],
            },
            {
                "method": "traditional_template",
                "n": 183132,
                "charge_res68_abs_frac": 0.12077766801970549,
                "run_block_charge_res68_abs_frac_ci95": [
                    0.11616875861201786,
                    0.1248512145266728,
                ],
            },
        ],
        "pseudo_saturation_recovery_median_by_method": [
            {
                "method": "ml_ratio_transfer",
                "res68_abs_frac": 0.03669062665507541,
            },
            {"method": "observed_raw", "res68_abs_frac": 0.3548387096774194},
            {"method": "traditional_template", "res68_abs_frac": 0.2},
        ],
    }
    manifest = {
        "ticket": result["ticket_id"],
        "study": "P07e",
        "git_commit": "f20e1b0bceac4eeae4532c9e871a363d6dce08d7",
        "outputs": {},
    }
    return report, result, manifest


def aligned_row() -> dict[str, str]:
    row = {field: "" for field in MOD.EXPECTED_LEDGER_FIELDS}
    row.update(
        {
            "claim_id": "CL-016",
            "chapter": "Energy",
            "section": "7",
            "claim_text": MOD.EXPECTED_CLAIM_TEXT,
            "current_value": "0.1763577793605039",
            "unit": "fraction",
            "ci_low": "0.17304334869529975",
            "ci_high": "0.18060166173702746",
            "ci_level": "0.95",
            "ci_method": "run_block_bootstrap_percentile",
            "bootstrap_unit": "run",
            "n_events": "183132",
            "n_runs": "33",
            "n_data": "183132",
            "baseline_value": "0.12079374117700271",
            "delta_vs_baseline": "0.05556403818350119",
            "truth_type": "data_external_duplicate_readout",
            "status": "GATED",
            "allowed_status_validated": "YES",
            "source_report": MOD.EXPECTED_PATHS["source_report"],
            "source_script": MOD.EXPECTED_PATHS["source_script"],
            "source_data": MOD.EXPECTED_PATHS["source_data"],
            "source_config": MOD.EXPECTED_PATHS["source_config"],
            "source_manifest": MOD.EXPECTED_PATHS["source_manifest"],
            "link_validated": "YES",
            "ci_status": "CI_AVAILABLE_PRODUCER_BYTES_UNBOUND",
            "blocked_by": "BLK-P07E-001",
            "notes": "External duplicate closure vetoes applying the ML correction.",
        }
    )
    return row


def write_ledger(path: Path, *, malformed: bool = False) -> None:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(MOD.EXPECTED_LEDGER_FIELDS)
    if malformed:
        writer.writerow(
            [
                "CL-016",
                "Energy",
                "7",
                "Saturation recovery ML",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "data_only",
                "GATED",
                "YES",
                "reports/p07e_saturation/REPORT.md",
                "scripts/p07e_saturation.py",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "CI_MISSING_BLOCKING",
                "",
                "",
                "Need exact metric/baseline/ML/delta/CI/leakage controls",
            ]
        )
    else:
        row = aligned_row()
        writer.writerow([row[field] for field in MOD.EXPECTED_LEDGER_FIELDS])
    path.write_text(stream.getvalue(), encoding="utf-8")


def make_fixture(tmp_path: Path, *, malformed: bool, bound: bool) -> tuple[Path, Path, Path, Path]:
    ledger = tmp_path / "claim_ledger.csv"
    report_path = tmp_path / "REPORT.md"
    result_path = tmp_path / "result.json"
    manifest_path = tmp_path / "manifest.json"
    write_ledger(ledger, malformed=malformed)
    report, result, manifest = source_payload()
    report_path.write_text(report, encoding="utf-8")
    write_json(result_path, result)
    manifest["outputs"] = {
        "REPORT.md": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "result.json": hashlib.sha256(result_path.read_bytes()).hexdigest(),
    }
    if bound:
        manifest["producer_sha256"] = "a" * 64
        manifest["worktree_clean"] = True
    write_json(manifest_path, manifest)
    return ledger, report_path, result_path, manifest_path


def test_current_like_ledger_and_manifest_fail_closed(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path, malformed=True, bound=False)
    result = MOD.audit(*paths)
    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] == "FLAWED"
    assert result["scientific_decision"] == "WITHHOLD_ML_CORRECTION"
    assert "LEDGER_ROW_WIDTH_MISMATCH" in codes
    assert "PRODUCER_BYTES_NOT_HASH_BOUND" in codes
    assert "WORKTREE_STATE_NOT_RECORDED_CLEAN" in codes
    assert result["scientific_basis"][
        "external_ml_worse_than_raw_with_nonoverlapping_run_block_ci95"
    ]


def test_aligned_hash_bound_chain_validates_and_preserves_harm_veto(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path, malformed=False, bound=True)
    result = MOD.audit(*paths)
    assert result["status"] == "VALIDATED"
    assert result["n_findings"] == 0
    basis = result["scientific_basis"]
    assert math.isclose(
        basis["ml_minus_raw_charge_res68_abs_frac"],
        0.05556403818350119,
        rel_tol=0.0,
        abs_tol=1e-15,
    )
    assert basis["pseudo_saturation_ml_res68_abs_frac"] == 0.03669062665507541
    assert result["scientific_decision"] == "WITHHOLD_ML_CORRECTION"


def test_manifest_output_hash_mismatch_is_detected(tmp_path: Path) -> None:
    ledger, report, result_path, manifest_path = make_fixture(
        tmp_path,
        malformed=False,
        bound=True,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"]["result.json"] = "0" * 64
    write_json(manifest_path, manifest)
    result = MOD.audit(ledger, report, result_path, manifest_path)
    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] == "FLAWED"
    assert "MANIFEST_OUTPUT_HASH_MISMATCH" in codes


def test_cli_writes_machine_readable_and_visual_evidence(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path, malformed=True, bound=False)
    output = tmp_path / "audit.json"
    svg = tmp_path / "audit.svg"
    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            *(str(path) for path in paths),
            "--output",
            str(output),
            "--svg",
            str(svg),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "FLAWED"
    assert "P07e saturation recovery evidence hierarchy" in svg.read_text(encoding="utf-8")
