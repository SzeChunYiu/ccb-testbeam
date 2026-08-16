from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "audit_tau_eff_claim_binding.py"
SPEC = importlib.util.spec_from_file_location("audit_tau_eff_claim_binding", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COUNTS = [
    2038,
    24333,
    687,
    5276,
    14000,
    14815,
    35217,
    14740,
    7152,
    32200,
    30440,
    17387,
    40148,
    13833,
]
VALUES = [
    119.71824180400847,
    122.6893680247759,
    124.5257754243097,
    126.05149737576761,
    122.42656081010601,
    123.19633347019185,
    126.85994574444646,
    124.10559622654579,
    125.21984881414237,
    127.43600416469366,
    130.02590368229406,
    123.21455937684186,
    129.59650229233844,
    121.99643798642357,
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_heldout(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["heldout_run", "n_pulses", "traditional_template_live10_ns"])
        for run, count, value in zip(range(44, 58), COUNTS, VALUES):
            writer.writerow([run, count, repr(value)])


def _result() -> dict:
    return {
        "study": "S10b",
        "ticket": "1781000867.546870.5c124aaf",
        "traditional": {
            "tau_eff_live10_ns": 124.79018394263471,
            "tau_eff_live10_ci95_ns": [123.33094981246663, 126.35875117626817],
        },
        "git_commit": MODULE.EXPECTED_COMMIT,
    }


def _corrected_row() -> dict[str, str]:
    row = {field: "" for field in MODULE.EXPECTED_FIELDS}
    row.update(
        {
            "claim_id": "CL-011",
            "chapter": "Pile-up",
            "section": "5",
            "claim_text": MODULE.EXPECTED_CLAIM_TEXT,
            "current_value": "124.79018394263471",
            "unit": "ns",
            "ci_low": "123.33094981246663",
            "ci_high": "126.35875117626817",
            "ci_level": "0.95",
            "ci_method": MODULE.EXPECTED_CI_METHOD,
            "bootstrap_unit": "run",
            "n_runs": "14",
            "n_data": "252266",
            "truth_type": MODULE.EXPECTED_TRUTH_TYPE,
            "status": MODULE.EXPECTED_STATUS,
            "allowed_status_validated": "NO",
            "source_report": MODULE.PRIMARY["report"],
            "source_script": MODULE.PRIMARY["script"],
            "source_data": MODULE.PRIMARY["result"],
            "source_manifest": MODULE.PRIMARY["manifest"],
            "source_commit": MODULE.EXPECTED_COMMIT,
            "link_validated": "YES",
            "ci_status": MODULE.EXPECTED_CI_STATUS,
            "blocked_by": MODULE.EXPECTED_BLOCKER,
            "supersedes": "90 ns",
            "notes": (
                "This is a run-average estimand across 14 runs and 252266 selected pulses; "
                "it is not a detector-wide universal dead time. MV5 uses the value as an "
                "input rather than independently validating it. The source provides a "
                "run-bootstrap interval but no statistical/systematic uncertainty decomposition."
            ),
        }
    )
    return row


def _current_row() -> dict[str, str]:
    values = next(
        csv.reader(
            [
                "CL-011,Pile-up,5,Effective live-time tau_eff,124.79,ns,0.5,1.0,1.12,"
                "123.5,126.0,0.95,bootstrap,run,,,213843,,,,,,,,,,,"
                "data_mc_self_consistent,VALIDATED,YES,"
                "reports/mv5_pileup_1782678353/REPORT.md,scripts/mv5_pileup_study.py,"
                "reports/mv5_pileup_1782678353/results.json,,,FIG-PU-002,,,,"
                "CI_MISSING_BLOCKING,,90 ns,"
                '"Need alternative method cross-check; truth type was data_only, upgraded '
                'to data+MC self-consistent per audit"'
            ]
        )
    )
    assert len(values) == len(MODULE.EXPECTED_FIELDS)
    return dict(zip(MODULE.EXPECTED_FIELDS, values))


def _write_ledger(path: Path, row: dict[str, str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MODULE.EXPECTED_FIELDS)
        writer.writeheader()
        writer.writerow(row)


def _fixture(tmp_path: Path, row: dict[str, str]) -> tuple[Path, Path, Path, Path, Path]:
    ledger = tmp_path / "claim_ledger.csv"
    result = tmp_path / "result.json"
    manifest = tmp_path / "manifest.json"
    heldout = tmp_path / "heldout_run_summary.csv"
    report = tmp_path / "REPORT.md"
    _write_ledger(ledger, row)
    result.write_text(json.dumps(_result(), indent=2) + "\n", encoding="utf-8")
    _write_heldout(heldout)
    report.write_text("# S10b\nPrimary data measurement.\n", encoding="utf-8")
    manifest.write_text(
        json.dumps(
            {
                "git_commit": MODULE.EXPECTED_COMMIT,
                "outputs": {
                    "result.json": _sha(result),
                    "heldout_run_summary.csv": _sha(heldout),
                    "REPORT.md": _sha(report),
                    "s10b_tau_eff_template_fit.py": (
                        "975ad0e5fdd70b92ab113c35160e3dc6bf30f49600af739ba0c24d4ef689036f"
                    ),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return ledger, result, manifest, heldout, report


def test_current_like_cl011_fails_with_provenance_and_semantics_findings(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, _current_row())
    payload = MODULE.audit(*paths)
    assert payload["status"] == "FLAWED"
    codes = {issue["code"] for issue in payload["issues"]}
    assert "SECONDARY_MV5_REPORT_USED_AS_PRIMARY_SOURCE" in codes
    assert "NONEXISTENT_LEDGER_SOURCE_DATA_PATH" in codes
    assert "UNSUPPORTED_UNCERTAINTY_DECOMPOSITION" in codes
    assert "INDEPENDENT_CLOSURE_OVERSTATED" in codes
    assert payload["source_facts"]["selected_pulse_count"] == 252266
    assert payload["source_facts"]["run_count"] == 14


def test_corrected_contract_validates(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, _corrected_row())
    payload = MODULE.audit(*paths)
    assert payload["status"] == "VALIDATED"
    assert payload["issues"] == []


def test_manifest_hash_mutation_fails(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, _corrected_row())
    paths[1].write_text(paths[1].read_text(encoding="utf-8") + " ", encoding="utf-8")
    payload = MODULE.audit(*paths)
    assert payload["status"] == "FLAWED"
    assert any(issue["code"] == "MANIFEST_OUTPUT_HASH_MISMATCH" for issue in payload["issues"])


def test_duplicate_cl011_fails_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, _corrected_row())
    with paths[0].open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MODULE.EXPECTED_FIELDS)
        writer.writerow(_corrected_row())
    payload = MODULE.audit(*paths)
    assert payload["status"] == "FLAWED"
    assert payload["issues"][0]["code"] == "CL011_CARDINALITY"


def test_cli_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    paths = list(_fixture(tmp_path, _corrected_row()))
    paths[0].write_bytes(b"\xff")
    proc = subprocess.run(
        [sys.executable, str(MODULE_PATH), *map(str, paths)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "not valid UTF-8" in proc.stderr


def test_cli_rejects_output_alias_and_preserves_input(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, _corrected_row())
    before = paths[1].read_bytes()
    proc = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            *map(str, paths),
            "--output",
            str(paths[1]),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert paths[1].read_bytes() == before
