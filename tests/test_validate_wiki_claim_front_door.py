from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools/audit/validate_wiki_claim_front_door.py"
SPEC = importlib.util.spec_from_file_location("validate_wiki_claim_front_door", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_ledger(path: Path, *, raw_status: str = "VALIDATED") -> None:
    fields = [
        "claim_id",
        "status",
        "truth_type",
        "stat_unc",
        "syst_unc",
        "ci_status",
    ]
    rows = [
        {
            "claim_id": "CL-007",
            "status": raw_status,
            "truth_type": "digitized_mc",
            "stat_unc": "CI_MISSING_BLOCKING",
            "syst_unc": "CI_MISSING_BLOCKING",
            "ci_status": "CI_MISSING_BLOCKING",
        },
        {
            "claim_id": "CL-011",
            "status": "VALIDATED",
            "truth_type": "data_mc_self_consistent",
            "stat_unc": "0.5",
            "syst_unc": "1.0",
            "ci_status": "CI_MISSING_BLOCKING",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def wiki_text(*, raw_status: str, tau_truth: str, overclaim: bool) -> str:
    preface = "> Every number has uncertainty.\n" if overclaim else (
        "> Missing uncertainties are explicitly marked in the canonical claim ledger.\n"
    )
    return preface + f"""
### Confidence-Status Legend
| Label | Meaning |
|---|---|
| **VALIDATED** | supported |
| **DONE_DATA_ONLY** | data only |
| **TRUTH_LEVEL_MC_ONLY** | MC only |
| **TENSION** | tension |
| **FAIL** | failure |
| **CORRECTED** | corrected |
| **BLOCKED** | blocked |
| **GATED** | gated |

### Canonical Results Table
| Claim | Current value | Stat. unc. | Syst. unc. | Truth type | Status |
|---|---|---|---|---|---|
| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 | {tau_truth} | **VALIDATED** |
| MV4 raw timing pull | −1.05σ | — | — | digitized MC | **{raw_status}** |

### Key Results
| Observable | Value | Status |
|---|---|---|
| τeff (effective live-time) | 124.79 ns | **VALIDATED** |
| MC raw timing pull | −1.05σ | **{raw_status}** |

### Validation Matrix
| Study | Observable | Verdict | Action |
|---|---|---|---|
| MV4 raw | Timing | **{raw_status}** (−1.05σ) | Accept |
"""


def test_current_front_door_defects_are_detected(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(
        wiki_text(raw_status="PASS", tau_truth="data_only", overclaim=True),
        encoding="utf-8",
    )
    write_ledger(ledger)

    result = MODULE.audit(wiki, ledger)
    codes = [issue["code"] for issue in result["issues"]]

    assert result["status"] == "FLAWED"
    assert codes.count("STATUS_OUTSIDE_LEGEND") == 3
    assert codes.count("STATUS_LEDGER_MISMATCH") == 3
    assert codes.count("TRUTH_TYPE_LEDGER_MISMATCH") == 1
    assert codes.count("OVERSTATED_UNCERTAINTY_COMPLETENESS") == 1


def test_corrected_front_door_matches_ledger(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(
        wiki_text(
            raw_status="VALIDATED",
            tau_truth="data + MC self-consistent",
            overclaim=False,
        ),
        encoding="utf-8",
    )
    write_ledger(ledger)

    result = MODULE.audit(wiki, ledger)

    assert result["status"] == "VALIDATED"
    assert result["issues"] == []


def test_missing_required_claim_is_controlled_error(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(
        wiki_text(
            raw_status="VALIDATED",
            tau_truth="data + MC self-consistent",
            overclaim=False,
        ),
        encoding="utf-8",
    )
    write_ledger(ledger)
    lines = ledger.read_text(encoding="utf-8").splitlines()
    ledger.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")

    with pytest.raises(MODULE.WikiClaimAuditError, match="CL-011"):
        MODULE.audit(wiki, ledger)


def test_cli_writes_machine_readable_flaw_record(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    output = tmp_path / "result.json"
    wiki.write_text(
        wiki_text(raw_status="PASS", tau_truth="data_only", overclaim=True),
        encoding="utf-8",
    )
    write_ledger(ledger)

    status = MODULE.main([str(wiki), str(ledger), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert status == 1
    assert payload["status"] == "FLAWED"
    assert payload["n_issues"] == 8


def test_invalid_utf8_returns_status_two(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_bytes(b"\xff")
    write_ledger(ledger)

    assert MODULE.main([str(wiki), str(ledger)]) == 2
