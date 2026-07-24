from __future__ import annotations

import csv
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "validate_wiki_canonical_results.py"
SPEC = importlib.util.spec_from_file_location("validate_wiki_canonical_results", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
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

ROWS = {
    "CL-002": ("", "", "", "legacy_claim_source_unresolved", "BLOCKED"),
    "CL-004": ("", "", "", "legacy_claim_source_unresolved", "BLOCKED"),
    "CL-006": ("", "", "", "legacy_claim_source_unresolved", "BLOCKED"),
    "CL-011": ("124.79", "0.5", "1.0", "data_mc_self_consistent", "VALIDATED"),
    "CL-013": ("92", "", "28", "data_mc_calibration_proxy", "GATED"),
    "CL-017": ("0.9859658513538254", "", "", "mc_truth_only", "GATED"),
    "CL-022": ("0.003232254011764034", "", "", "mc_truth_only", "TRUTH_LEVEL_MC_ONLY"),
    "CL-021": ("68269.4", "", "", "legacy_data_mc_profile_diagnostic", "FLAWED"),
    "CL-007": ("-1.054403396247793", "", "", "legacy_toy_digitizer_diagnostic", "GATED"),
    "CL-008": ("2.680528799917713", "", "", "legacy_toy_digitizer_diagnostic", "GATED"),
    "CL-009": ("REVIEW", "", "", "legacy_toy_digitizer_diagnostic", "REVIEW"),
}


def ledger_text(width_override: dict[str, int] | None = None) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(HEADER)
    for claim_id, (value, stat, syst, truth, status) in ROWS.items():
        row = {field: "" for field in HEADER}
        row.update({
            "claim_id": claim_id,
            "current_value": value,
            "unit": "ns" if claim_id in {"CL-002", "CL-004", "CL-011"} else "",
            "stat_unc": stat,
            "syst_unc": syst,
            "truth_type": truth,
            "status": status,
        })
        values = [row[field] for field in HEADER]
        if width_override and claim_id in width_override:
            values = values[:width_override[claim_id]]
        writer.writerow(values)
    return stream.getvalue()


VALID_WIKI = "\n".join(
    [
        "# WIKI",
        "### Confidence-Status Legend",
        "| Label | Meaning |",
        "|---|---|",
        "| **VALIDATED** | x |",
        "| **TRUTH_LEVEL_MC_ONLY** | x |",
        "| **FLAWED** | x |",
        "| **BLOCKED** | x |",
        "| **GATED** | x |",
        "| **REVIEW** | x |",
        "",
        "### Canonical Results Table",
        "| Claim | Current value | Stat. unc. | Syst. unc. | Truth type | Status |",
        "|---|---|---|---|---|---|",
        (
            "| B6 single-stave σ₆₈ | Withheld pending BLK-MV4-LEGACY-001 | "
            "— | — | legacy claim source unresolved | **BLOCKED** |"
        ),
        (
            "| Combined 3-stave σ (B4+B6+B8) | Withheld pending "
            "BLK-MV4-LEGACY-001 | — | — | legacy claim source unresolved | "
            "**BLOCKED** |"
        ),
        (
            "| Pair covariance | Withheld pending BLK-MV4-LEGACY-001 | — | — | "
            "legacy claim source unresolved | **BLOCKED** |"
        ),
        (
            "| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 | "
            "data + MC self-consistent | **VALIDATED** |"
        ),
        (
            "| Digitizer gain (MV0 v2) | 92 ADC/MeV | — | 28 | "
            "data + MC calibration proxy | **GATED** |"
        ),
        "| p/d PID AUC | 0.9860 | — | — | MC truth only | **GATED** |",
        (
            "| C12-like anomaly fraction in truth-labelled MC | "
            "283 / 87,555 tracks (0.32%) | — | — | MC truth only | "
            "**TRUTH_LEVEL_MC_ONLY** |"
        ),
        (
            "| MV3 legacy B8 fractions / profile statistic | data 2.3%; MC 22.3%; "
            "reported χ²/ndf label 68269.4 | — | — | "
            "legacy data/MC profile diagnostic | **FLAWED** |"
        ),
        (
            "| MV4 raw timing pull | -1.05σ | — | — | "
            "legacy toy-digitizer diagnostic | **GATED** |"
        ),
        (
            "| MV4 corrected timing pull | +2.68σ | — | — | "
            "legacy toy-digitizer diagnostic | **GATED** |"
        ),
        (
            "| ML timing | REVIEW diagnostic | — | — | "
            "legacy toy-digitizer diagnostic | **REVIEW** |"
        ),
        "",
        "### Corrected Values (Historical Context Only)",
        "| Old value | New canonical value | Reason |",
        "|---|---|---|",
        (
            "| PCA 3 PCs 89%, 8 PCs 99.7% | PCA 3 PCs 72.546%, "
            "8 PCs 82.188% (synthetic-waveform MC only) | "
            "Source-backed MV6 output |"
        ),
        "",
    ]
)


def test_valid_canonical_table_matches_exact_width_rows(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(VALID_WIKI, encoding="utf-8")
    ledger.write_text(ledger_text(), encoding="utf-8")
    result = MODULE.audit(wiki, ledger)
    assert result["status"] == "VALIDATED"
    assert result["n_issues"] == 0


def test_stale_public_table_is_detected(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    stale = VALID_WIKI.replace(
        (
            "Withheld pending BLK-MV4-LEGACY-001 | — | — | "
            "legacy claim source unresolved | **BLOCKED**"
        ),
        "0.68–0.75 ns | 0.02 | 0.05 | data + digitized MC | **VALIDATED**",
        1,
    )
    wiki.write_text(stale, encoding="utf-8")
    ledger.write_text(ledger_text(), encoding="utf-8")
    result = MODULE.audit(wiki, ledger)
    codes = {issue["code"] for issue in result["issues"]}
    assert "STATUS_LEDGER_MISMATCH" in codes
    assert "TRUTH_TYPE_LEDGER_MISMATCH" in codes
    assert "VALUE_NOT_WITHHELD" in codes
    assert "UNSUPPORTED_WIKI_UNCERTAINTY" in codes


def test_gain_statistical_uncertainty_and_status_mismatch_are_detected(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    stale = VALID_WIKI.replace(
        (
            "| Digitizer gain (MV0 v2) | 92 ADC/MeV | — | 28 | "
            "data + MC calibration proxy | **GATED** |"
        ),
        "| Digitizer gain (MV0 v2) | 92 ± 28 ADC/MeV | 14 | 28 | digitized MC | **VALIDATED** |",
    )
    wiki.write_text(stale, encoding="utf-8")
    ledger.write_text(ledger_text(), encoding="utf-8")
    result = MODULE.audit(wiki, ledger)
    codes = {issue["code"] for issue in result["issues"]}
    assert "STATUS_LEDGER_MISMATCH" in codes
    assert "TRUTH_TYPE_LEDGER_MISMATCH" in codes
    assert "UNSUPPORTED_WIKI_UNCERTAINTY" in codes


def test_required_claim_width_mismatch_fails_closed(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_text(VALID_WIKI, encoding="utf-8")
    ledger.write_text(ledger_text({"CL-007": 42}), encoding="utf-8")
    try:
        MODULE.audit(wiki, ledger)
    except MODULE.WikiCanonicalResultsError as exc:
        assert "CL-007 has 42 columns" in str(exc)
    else:
        raise AssertionError("expected fail-closed schema error")


def test_cli_writes_machine_readable_flaw_result(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    output = tmp_path / "audit.json"
    wiki.write_text(VALID_WIKI.replace("| **REVIEW** | x |\n", ""), encoding="utf-8")
    ledger.write_text(ledger_text(), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH), str(wiki), str(ledger), "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "FLAWED"
    assert any(issue["code"] == "MISSING_REVIEW_LEGEND_STATUS" for issue in payload["issues"])


def test_invalid_utf8_returns_controlled_status_two(tmp_path: Path) -> None:
    wiki = tmp_path / "WIKI.md"
    ledger = tmp_path / "claim_ledger.csv"
    wiki.write_bytes(b"\xff")
    ledger.write_text(ledger_text(), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH), str(wiki), str(ledger)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "not valid UTF-8" in completed.stderr
