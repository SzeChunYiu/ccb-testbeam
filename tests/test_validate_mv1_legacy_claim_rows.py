from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "validate_mv1_legacy_claim_rows.py"
SPEC = importlib.util.spec_from_file_location("mv1_claim_validator", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HEADER = [
    "claim_id", "chapter", "section", "claim_text", "current_value", "unit",
    "stat_unc", "syst_unc", "total_unc", "ci_low", "ci_high", "ci_level",
    "ci_method", "bootstrap_unit", "n_events", "n_runs", "n_data", "n_mc",
    "numerator", "denominator", "p_value", "effect_size", "baseline_value",
    "baseline_unc", "delta_vs_baseline", "delta_ci_low", "delta_ci_high",
    "truth_type", "status", "allowed_status_validated", "source_report",
    "source_script", "source_data", "source_config", "source_manifest",
    "figure_ids", "table_ids", "source_commit", "link_validated", "ci_status",
    "blocked_by", "supersedes", "notes",
]

NOTE = (
    "Fixed legacy output from truth-labelled MC on 296972 proton/deuteron tracks. "
    "The producer splits by row-index parity rather than event groups, creating "
    "event-group leakage risk when an event contributes multiple tracks. It records "
    "no uncertainty or confidence interval. The current module uses a group-disjoint "
    "event_id split, but the old sample was not rerun. This is no beam-data PID "
    "performance result."
)


def _row(claim_id: str, value: str, text: str) -> list[str]:
    row = [""] * len(HEADER)
    values = {
        "claim_id": claim_id,
        "chapter": "PID",
        "section": "8",
        "claim_text": text,
        "current_value": value,
        "unit": "dimensionless",
        "n_mc": "296972",
        "truth_type": "mc_truth_only",
        "status": "GATED",
        "allowed_status_validated": "NO",
        "source_script": "scripts/mv1_mv2_truth_pid_energy.py",
        "source_data": (
            "reports/mv1_mv2_truth_pid_energy_1782220258/"
            "mv1_mv2_truth_summary.json"
        ),
        "figure_ids": "FIG-PID-001",
        "table_ids": "TAB-PID-001",
        "source_commit": "3539ae3aad222284bd7be100802a2651c0e064de",
        "link_validated": "YES",
        "ci_status": "NOT_EVALUATED_LEGACY_ROW_INDEX_SPLIT",
        "blocked_by": "BLK-MV1-001",
        "notes": NOTE,
    }
    for key, value_ in values.items():
        row[HEADER.index(key)] = value_
    return row


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    ledger = tmp_path / "ledger.csv"
    with ledger.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerow(
            _row(
                "CL-017",
                "0.9859658513538254",
                "Legacy truth-MC HGB p/d ROC AUC (row-index split)",
            )
        )
        writer.writerow(
            _row(
                "CL-018",
                "0.9644090769970706",
                (
                    "Legacy truth-MC HGB p/d purity at nominal 90% efficiency "
                    "(row-index split)"
                ),
            )
        )
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "n_tracks": 400369,
                "n_proton": 150130,
                "n_deuteron": 146842,
                "MV1_pid": {
                    "hgb_auc": 0.9859658513538254,
                    "hgb_purity_at_90eff": 0.9644090769970706,
                },
            }
        )
    )
    producer = tmp_path / "producer.py"
    producer.write_text(
        "rec={'pdg': [], 'edep_l0': []}\n"
        "idx=np.arange(n); tr=idx%2==0; te=~tr\n"
        "gb=HistGradientBoostingClassifier().fit(X[tr],y[tr])\n"
    )
    return ledger, summary, producer


def test_valid_legacy_governance_contract(tmp_path: Path) -> None:
    ledger, summary, producer = _write_inputs(tmp_path)
    result = MODULE.validate(ledger, summary, producer)
    assert result["status"] == "VALIDATED"
    assert result["n_issues"] == 0
    assert result["legacy_source_contract"] == {
        "row_index_parity_split": True,
        "event_id_recorded": False,
        "hgb_random_state_explicit": False,
    }


def test_wrong_auc_is_rejected(tmp_path: Path) -> None:
    ledger, summary, producer = _write_inputs(tmp_path)
    text = ledger.read_text().replace("0.9859658513538254", "0.99", 1)
    ledger.write_text(text)
    result = MODULE.validate(ledger, summary, producer)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "VALUE" for issue in result["issues"])


def test_width_mismatch_fails_closed(tmp_path: Path) -> None:
    ledger, summary, producer = _write_inputs(tmp_path)
    rows = list(csv.reader(ledger.open()))
    rows[1] = rows[1][:-1]
    with ledger.open("w", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)
    result = MODULE.validate(ledger, summary, producer)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "ROW_WIDTH" for issue in result["issues"])


def test_missing_parity_split_is_rejected(tmp_path: Path) -> None:
    ledger, summary, producer = _write_inputs(tmp_path)
    producer.write_text(
        "rec={'pdg': [], 'edep_l0': [], 'event_id': []}\n"
        "gb=HistGradientBoostingClassifier(random_state=0)\n"
    )
    result = MODULE.validate(ledger, summary, producer)
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "FLAWED"
    assert "LEGACY_SPLIT_NOT_DETECTED" in codes
    assert "EVENT_GROUP_KEY_PRESENT" in codes
    assert "RANDOM_STATE_PRESENT" in codes


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    ledger, summary, producer = _write_inputs(tmp_path)
    producer.write_bytes(b"\xff")
    try:
        MODULE.validate(ledger, summary, producer)
    except MODULE.Mv1ClaimError as exc:
        assert "not valid UTF-8" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid UTF-8 was accepted")


def test_cli_writes_machine_readable_result(tmp_path: Path) -> None:
    ledger, summary, producer = _write_inputs(tmp_path)
    output = tmp_path / "validation.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            str(ledger),
            str(summary),
            str(producer),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    payload = json.loads(output.read_text())
    assert payload["status"] == "VALIDATED"
    assert payload["n_issues"] == 0
