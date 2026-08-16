from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools/audit/validate_executive_summary_claims.py"
SPEC = importlib.util.spec_from_file_location("validate_executive_summary_claims", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_ledger(path: Path, *, malformed_claim: str | None = None) -> None:
    fields = ["claim_id"] + [f"field_{index}" for index in range(1, 27)] + [
        "truth_type",
        "status",
    ] + [f"field_{index}" for index in range(29, 43)]
    rows = [
        ("CL-010", "derived_model_conflicted", "BLOCKED"),
        ("CL-011", "data_mc_self_consistent", "VALIDATED"),
        ("CL-007", "digitized_mc", "VALIDATED"),
        ("CL-015", "data_external_duplicate_readout", "GATED"),
        ("CL-016", "data_external_duplicate_readout", "GATED"),
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        for claim_id, truth_type, status in rows:
            row = [""] * 43
            row[0] = claim_id
            row[27] = truth_type
            row[28] = status
            if claim_id == malformed_claim:
                row.pop()
            writer.writerow(row)


def markdown_row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |"


def corrected_summary() -> str:
    rows = [
        markdown_row(
            "Claim",
            "Current value",
            "Stat. unc.",
            "Syst. unc.",
            "Truth type",
            "Source study",
            "Status",
        ),
        markdown_row("---", "---", "---", "---", "---", "---", "---"),
        markdown_row(
            "Rmax (pile-up tolerance)",
            "Withheld — canonical criterion unresolved",
            "—",
            "—",
            "derived model (conflicted)",
            "MV5",
            "**BLOCKED**",
        ),
        markdown_row(
            "τeff (effective live-time)",
            "124.79 ns",
            "0.5",
            "1.0",
            "data + MC self-consistent",
            "MV5",
            "**VALIDATED**",
        ),
        markdown_row(
            "C12-like anomaly fraction in truth-labelled MC",
            "283 / 87,555 tracks (0.32%)",
            "—",
            "—",
            "MC truth only",
            "MV6",
            "**TRUTH_LEVEL_MC_ONLY**",
        ),
        markdown_row(
            "MV4 raw timing pull",
            "−1.05σ",
            "—",
            "—",
            "digitized MC",
            "MV4",
            "**VALIDATED**",
        ),
        markdown_row(
            "ML duplicate-readout selection",
            "No canonical winner; coverage interval crosses the gate",
            "—",
            "—",
            "data external duplicate readout",
            "P04p",
            "**GATED**",
        ),
        markdown_row(
            "ML saturation recovery",
            "Withheld; held-out closure is worse than raw",
            "—",
            "—",
            "data external duplicate readout",
            "P07e",
            "**GATED**",
        ),
    ]
    return "\n".join(rows) + "\n"


def stale_summary() -> str:
    rows = [
        markdown_row(
            "Claim",
            "Current value",
            "Stat. unc.",
            "Syst. unc.",
            "Truth type",
            "Source study",
            "Status",
        ),
        markdown_row("---", "---", "---", "---", "---", "---", "---"),
        markdown_row(
            "Rmax (pile-up tolerance)",
            "3.044–3.05 MHz",
            "0.05",
            "0.10",
            "data + MC",
            "MV5",
            "**VALIDATED**",
        ),
        markdown_row(
            "τeff (effective live-time)",
            "124.79 ns",
            "0.5",
            "1.0",
            "data_only",
            "MV5",
            "**VALIDATED**",
        ),
        markdown_row(
            "C12-like anomaly fraction in truth-labelled MC",
            "0.32%",
            "—",
            "—",
            "MC-identified",
            "MV6",
            "**VALIDATED**",
        ),
        markdown_row(
            "MV4 raw timing pull",
            "−1.05σ",
            "—",
            "—",
            "digitized MC",
            "MV4",
            "**PASS**",
        ),
        markdown_row(
            "ML wins (confirmed)",
            "Duplicate readout, saturation recovery",
            "—",
            "—",
            "data_only",
            "P04p, P07e",
            "**GATED**",
        ),
        "✅ Pile-up tolerance Rmax ≈ 3.05 MHz (corrected from 4.22 MHz).",
        "✅ C12 nuclear recoil anomaly fraction is 0.32% of tracks (MC-identified).",
    ]
    return "\n".join(rows) + "\n"


def test_stale_front_door_is_rejected(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    ledger = tmp_path / "claim_ledger.csv"
    summary.write_text(stale_summary(), encoding="utf-8")
    write_ledger(ledger)

    result = MODULE.audit(summary, ledger)
    codes = [issue["code"] for issue in result["issues"]]

    assert result["status"] == "FLAWED"
    assert "EXECUTIVE_STATUS_MISMATCH" in codes
    assert codes.count("MISSING_EXECUTIVE_CLAIM_ROW") == 2
    assert codes.count("UNSUPPORTED_EXECUTIVE_STATEMENT") == 3
    assert "C12_MC_TRUTH_STATUS_MISSING" in codes


def test_corrected_front_door_is_validated(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    ledger = tmp_path / "claim_ledger.csv"
    summary.write_text(corrected_summary(), encoding="utf-8")
    write_ledger(ledger)

    result = MODULE.audit(summary, ledger)

    assert result["status"] == "VALIDATED"
    assert result["issues"] == []
    assert len(result["bindings_checked"]) == 5


def test_required_claim_must_have_exact_width(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    ledger = tmp_path / "claim_ledger.csv"
    summary.write_text(corrected_summary(), encoding="utf-8")
    write_ledger(ledger, malformed_claim="CL-016")

    with pytest.raises(MODULE.ExecutiveSummaryAuditError, match="CL-016 has 42 columns"):
        MODULE.audit(summary, ledger)


def test_cli_writes_machine_readable_flaw_record(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    ledger = tmp_path / "claim_ledger.csv"
    output = tmp_path / "result.json"
    summary.write_text(stale_summary(), encoding="utf-8")
    write_ledger(ledger)

    status = MODULE.main([str(summary), str(ledger), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert status == 1
    assert payload["status"] == "FLAWED"
    assert payload["n_issues"] >= 8


def test_invalid_utf8_returns_status_two(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    ledger = tmp_path / "claim_ledger.csv"
    summary.write_bytes(b"\xff")
    write_ledger(ledger)

    assert MODULE.main([str(summary), str(ledger)]) == 2
