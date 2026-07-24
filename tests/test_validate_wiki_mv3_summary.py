from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.audit.validate_wiki_mv3_summary import ValidationError, audit

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


def summary_payload() -> dict:
    return {
        "mc": {
            "counts": {"B2": 117213, "B4": 45507, "B6": 31145, "B8": 55619},
            "fractions": {
                "B2": 0.46982171201359607,
                "B4": 0.18240448285260777,
                "B6": 0.12483766494043706,
                "B8": 0.22293614019335908,
            },
            "n_above_threshold": 249484,
        },
        "data": {
            "all": {
                "counts": {"B2": 268576, "B4": 19284, "B6": 11834, "B8": 7051},
                "fractions": {
                    "B2": 0.8755676539144892,
                    "B4": 0.06286655039201942,
                    "B6": 0.03857927594581819,
                    "B8": 0.02298651974767315,
                },
                "n_events": 306745,
            }
        },
        "chi2_mc_vs_data_all": 204808.2179684494,
        "chi2_ndf": 3,
        "chi2_per_ndf": 68269.40598948313,
    }


def claim_row(claim_id: str) -> list[str]:
    row = {name: "" for name in HEADER}
    row["claim_id"] = claim_id
    row["blocked_by"] = "BLK-MV3-LEGACY-001"
    if claim_id == "CL-019":
        row.update({
            "current_value": "0.22293614019335908",
            "numerator": "55619",
            "denominator": "249484",
            "status": "GATED",
        })
    elif claim_id == "CL-020":
        row.update({
            "current_value": "0.02298651974767315",
            "numerator": "7051",
            "denominator": "306745",
            "status": "GATED",
        })
    else:
        row.update({"current_value": "68269.40598948313", "status": "FLAWED"})
    return [row[name] for name in HEADER]


def write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    summary = tmp_path / "mv3_summary.json"
    wiki.write_text(
        "data 7051/306745 = 0.02298651974767315; "
        "MC 55619/249484 = 0.22293614019335908; "
        "Pearson χ² = 204808.2179684494, ndf = 3, "
        "χ²/ndf = 68269.40598948313. "
        "The fixed-source arithmetic is reproducible, but the diagnostic remains "
        "FLAWED under BLK-MV3-LEGACY-001.\n",
        encoding="utf-8",
    )
    with ledger.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for claim_id in ("CL-019", "CL-020", "CL-021"):
            writer.writerow(claim_row(claim_id))
    summary.write_text(json.dumps(summary_payload()), encoding="utf-8")
    return wiki, ledger, summary


def test_valid_contract(tmp_path: Path) -> None:
    wiki, ledger, summary = write_inputs(tmp_path)
    payload = audit(wiki, ledger, summary)
    assert payload["status"] == "VALIDATED"
    assert payload["issues"] == []
    assert payload["reconstructed"]["chi2_ndf"] == 68269.40598948313


def test_stale_absence_narrative_fails(tmp_path: Path) -> None:
    wiki, ledger, summary = write_inputs(tmp_path)
    wiki.write_text(
        wiki.read_text(encoding="utf-8")
        + "Recover exact counts/statistic and rerun strict stopping-depth path\n",
        encoding="utf-8",
    )
    payload = audit(wiki, ledger, summary)
    assert payload["status"] == "FLAWED"
    assert any(issue["code"] == "STALE_MV3_ABSENCE_NARRATIVE" for issue in payload["issues"])


def test_altered_ledger_value_fails(tmp_path: Path) -> None:
    wiki, ledger, summary = write_inputs(tmp_path)
    text = ledger.read_text(encoding="utf-8").replace(
        "0.22293614019335908", "0.223", 1
    )
    ledger.write_text(text, encoding="utf-8")
    payload = audit(wiki, ledger, summary)
    assert payload["status"] == "FLAWED"
    assert any(issue["code"] == "LEDGER_SUMMARY_MISMATCH" for issue in payload["issues"])


def test_summary_arithmetic_mismatch_fails(tmp_path: Path) -> None:
    wiki, ledger, summary = write_inputs(tmp_path)
    payload = summary_payload()
    payload["chi2_per_ndf"] = 68269.4
    summary.write_text(json.dumps(payload), encoding="utf-8")
    result = audit(wiki, ledger, summary)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "SUMMARY_ARITHMETIC_MISMATCH" for issue in result["issues"])


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    wiki, ledger, summary = write_inputs(tmp_path)
    wiki.write_bytes(b"\xff")
    with pytest.raises(ValidationError, match="not valid UTF-8"):
        audit(wiki, ledger, summary)
