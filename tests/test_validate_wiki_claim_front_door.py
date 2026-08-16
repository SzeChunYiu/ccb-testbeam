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

FIELDS = [
    "claim_id",
    "chapter",
    "section",
    "claim_text",
    "current_value",
    "unit",
    "stat_unc",
    "syst_unc",
    "total_unc",
    "ci_low",
    "ci_high",
    "ci_level",
    "ci_method",
    "bootstrap_unit",
    "n_events",
    "n_runs",
    "n_data",
    "n_mc",
    "numerator",
    "denominator",
    "p_value",
    "effect_size",
    "baseline_value",
    "baseline_unc",
    "delta_vs_baseline",
    "delta_ci_low",
    "delta_ci_high",
    "truth_type",
    "status",
    "allowed_status_validated",
    "source_report",
    "source_script",
    "source_data",
    "source_config",
    "source_manifest",
    "figure_ids",
    "table_ids",
    "source_commit",
    "link_validated",
    "ci_status",
    "blocked_by",
    "supersedes",
    "notes",
]
assert len(FIELDS) == 43


def ledger_rows() -> list[dict[str, str]]:
    common = {field: "" for field in FIELDS}
    rows = []
    for values in (
        {
            "claim_id": "CL-007",
            "truth_type": "digitized_mc",
            "status": "VALIDATED",
            "stat_unc": "CI_MISSING_BLOCKING",
            "syst_unc": "CI_MISSING_BLOCKING",
            "ci_status": "CI_MISSING_BLOCKING",
        },
        {
            "claim_id": "CL-010",
            "unit": "MHz",
            "truth_type": "derived_model_conflicted",
            "status": "BLOCKED",
            "ci_status": "NOT_APPLICABLE_WITH_REASON",
            "blocked_by": "S-STAT-003",
        },
        {
            "claim_id": "CL-011",
            "current_value": "124.79",
            "unit": "ns",
            "truth_type": "data_mc_self_consistent",
            "status": "VALIDATED",
            "stat_unc": "0.5",
            "syst_unc": "1.0",
            "ci_status": "CI_MISSING_BLOCKING",
        },
        {
            "claim_id": "CL-012",
            "unit": "MHz",
            "truth_type": "derived_model_conflicted",
            "status": "SUPERSEDED",
            "ci_status": "SUPERSEDED_DO_NOT_USE",
            "blocked_by": "S-STAT-003",
        },
        {
            "claim_id": "CL-015",
            "current_value": "0.03902452880489024",
            "unit": "fraction",
            "truth_type": "data_external_duplicate_readout",
            "status": "GATED",
            "ci_status": "CI_AVAILABLE_SELECTION_GATE_UNSTABLE",
            "blocked_by": "BLK-P04P-001",
        },
        {
            "claim_id": "CL-016",
            "current_value": "0.1763577793605039",
            "unit": "fraction",
            "truth_type": "data_external_duplicate_readout",
            "status": "GATED",
            "ci_status": "CI_AVAILABLE_PRODUCER_BYTES_UNBOUND",
            "blocked_by": "BLK-P07E-001",
        },
    ):
        row = dict(common)
        row.update(values)
        rows.append(row)
    return rows


def write_ledger(
    path: Path,
    *,
    missing_claim: str | None = None,
    malformed_claim: str | None = None,
    malformed_delta: int = 0,
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        for row in ledger_rows():
            if row["claim_id"] == missing_claim:
                continue
            values = [row[field] for field in FIELDS]
            if row["claim_id"] == malformed_claim:
                if malformed_delta == -1:
                    values = values[:-1]
                elif malformed_delta == 1:
                    values.append("unexpected")
                else:
                    raise AssertionError("malformed_delta must be -1 or 1")
            writer.writerow(values)


def wiki_text(*, corrected: bool) -> str:
    if corrected:
        rmax_value = "Withheld pending S-STAT-003"
        rmax_truth = "derived model conflicted"
        rmax_status = "BLOCKED"
        historical = "Withheld pending S-STAT-003"
        duplicate_verdict = "**GATED** — no canonical production winner"
        saturation_verdict = "**GATED** — external duplicate closure is worse than raw"
        duplicate_value = "No production model authorized"
        saturation_value = "No production correction authorized"
        canonical_ml_rows = (
            "| Duplicate-readout model | No production model authorized | — | — | "
            "data external duplicate readout | **GATED** |\n"
            "| Saturation-recovery model | No production correction authorized | — | — | "
            "data external duplicate readout | **GATED** |"
        )
        executive = (
            "No production duplicate-readout or saturation correction is authorized.\n"
            "Rmax is withheld pending S-STAT-003."
        )
        derivation = "Rmax is withheld pending S-STAT-003."
        mv5_status = "BLOCKED"
    else:
        rmax_value = "3.044–3.05 MHz"
        rmax_truth = "data + MC self-consistent"
        rmax_status = "VALIDATED"
        historical = "~3.05 MHz"
        duplicate_verdict = "**ML wins** (GATED)"
        saturation_verdict = "**ML wins** (GATED)"
        duplicate_value = "Confirmed win domain"
        saturation_value = "Promising"
        canonical_ml_rows = (
            "| ML wins | Duplicate readout, saturation recovery | — | — | "
            "data_only | **GATED** |"
        )
        executive = (
            "ML excels where the missing information is genuinely in waveform shape "
            "(saturation recovery, duplicate-readout closure)."
        )
        derivation = """
The accepted pile-up tolerance uses **μ_max ≈ 0.38**.
Rmax = 0.38 / 124.79 ns = 3.04 MHz
"""
        mv5_status = "VALIDATED"

    return f"""
> Missing uncertainties are explicitly marked in the canonical claim ledger.

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
| Rmax (pile-up tolerance) | {rmax_value} | — | — | {rmax_truth} | **{rmax_status}** |
| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 | data + MC self-consistent | **VALIDATED** |
| MV4 raw timing pull | −1.05σ | — | — | digitized MC | **VALIDATED** |
{canonical_ml_rows}

### Corrected Values (Historical Context Only)
| Old value | New canonical value | Reason |
|---|---|---|
| 4.22 MHz | {historical} | definition conflict |

### Executive Verdict
{executive}

### Key Results
| Observable | Value | Status |
|---|---|---|
| Rmax (pile-up tolerance) | {rmax_value} | **{rmax_status}** |
| τeff (effective live-time) | 124.79 ns | **VALIDATED** |
| MC raw timing pull | −1.05σ | **VALIDATED** |

### Derivation Summary
{derivation}

### ML Verdict Matrix
| Domain | Traditional | ML | Verdict |
|---|---|---|---|
| Duplicate readout | Amplitude correlation | ML closure | {duplicate_verdict} |
| Saturation recovery | Clip rejection | ML recovery | {saturation_verdict} |

### Energy Results
| Observable | Value | Status |
|---|---|---|
| ML duplicate-readout | {duplicate_value} | **GATED** |
| ML saturation recovery | {saturation_value} | **GATED** |

### Validation Matrix
| Study | Observable | Verdict | Action |
|---|---|---|---|
| MV4 raw | Timing | **VALIDATED** (−1.05σ) | Accept |
| MV5 | Pile-up Rmax | **{mv5_status}** | Resolve S-STAT-003 |
"""


def test_current_rmax_and_ml_overclaims_are_detected(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(wiki_text(corrected=False), encoding="utf-8")
    write_ledger(ledger)

    result = MODULE.audit(wiki, ledger)
    codes = [issue["code"] for issue in result["issues"]]

    assert result["status"] == "FLAWED"
    assert codes.count("STATUS_LEDGER_MISMATCH") == 3
    assert "TRUTH_TYPE_LEDGER_MISMATCH" in codes
    assert codes.count("VALUE_PRESENT_WHEN_LEDGER_WITHHOLDS") == 3
    assert "UNRESOLVED_RMAX_THRESHOLD_PUBLISHED" in codes
    assert "UNRESOLVED_RMAX_DERIVATION_PUBLISHED" in codes
    assert "UNSUPPORTED_COMBINED_ML_WIN_CLAIM" in codes
    assert "UNSUPPORTED_ML_WIN_CLAIM" in codes
    assert codes.count("MISSING_REQUIRED_PUBLIC_CAVEAT") == 2


def test_corrected_front_door_matches_exact_width_ledger(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(wiki_text(corrected=True), encoding="utf-8")
    write_ledger(ledger)

    result = MODULE.audit(wiki, ledger)

    assert result["status"] == "VALIDATED"
    assert result["issues"] == []
    assert result["expected_ledger_columns"] == 43
    assert set(result["required_claim_widths"].values()) == {43}


def test_missing_required_claim_is_controlled_error(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(wiki_text(corrected=True), encoding="utf-8")
    write_ledger(ledger, missing_claim="CL-016")

    with pytest.raises(MODULE.WikiClaimAuditError, match="CL-016"):
        MODULE.audit(wiki, ledger)


@pytest.mark.parametrize("delta, expected", [(-1, 42), (1, 44)])
def test_bound_claim_wrong_width_fails_closed(
    tmp_path: Path,
    delta: int,
    expected: int,
) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(wiki_text(corrected=True), encoding="utf-8")
    write_ledger(
        ledger,
        malformed_claim="CL-016",
        malformed_delta=delta,
    )

    with pytest.raises(
        MODULE.WikiClaimAuditError,
        match=rf"CL-016 has {expected} columns; expected 43",
    ):
        MODULE.audit(wiki, ledger)


def test_noncanonical_header_width_fails_closed(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(wiki_text(corrected=True), encoding="utf-8")
    write_ledger(ledger)
    lines = ledger.read_text(encoding="utf-8").splitlines()
    rows = list(csv.reader(lines))
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(rows[0][:-1])
        writer.writerows(row[:-1] for row in rows[1:])

    with pytest.raises(MODULE.WikiClaimAuditError, match="header has 42 columns"):
        MODULE.audit(wiki, ledger)


def test_cli_writes_machine_readable_flaw_record(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    output = tmp_path / "result.json"
    wiki.write_text(wiki_text(corrected=False), encoding="utf-8")
    write_ledger(ledger)

    status = MODULE.main([str(wiki), str(ledger), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert status == 1
    assert payload["status"] == "FLAWED"
    assert payload["n_issues"] > 0
    assert payload["required_claim_widths"]["CL-016"] == 43


def test_cli_schema_error_returns_two_without_output(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    output = tmp_path / "result.json"
    wiki.write_text(wiki_text(corrected=True), encoding="utf-8")
    write_ledger(ledger, malformed_claim="CL-015", malformed_delta=-1)

    status = MODULE.main([str(wiki), str(ledger), "--output", str(output)])

    assert status == 2
    assert not output.exists()


def test_invalid_utf8_returns_status_two(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_bytes(b"\xff")
    write_ledger(ledger)

    assert MODULE.main([str(wiki), str(ledger)]) == 2


def test_former_v1_1_binding_scope_misses_rmax_and_ml_overclaims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(wiki_text(corrected=False), encoding="utf-8")
    write_ledger(ledger)
    monkeypatch.setattr(MODULE, "BINDINGS", MODULE.BINDINGS[:4])
    monkeypatch.setattr(MODULE, "FORBIDDEN_PUBLIC_PHRASES", ())
    monkeypatch.setattr(MODULE, "REQUIRED_PUBLIC_STATEMENTS", ())

    result = MODULE.audit(wiki, ledger)

    assert result["status"] == "VALIDATED"
    assert result["issues"] == []
