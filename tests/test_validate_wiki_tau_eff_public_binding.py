from __future__ import annotations

import csv
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path("tools/audit/validate_wiki_tau_eff_public_binding.py")
SPEC = importlib.util.spec_from_file_location("wiki_tau_eff", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HEADER = (
    "claim_id,chapter,section,claim_text,current_value,unit,stat_unc,syst_unc,"
    "total_unc,ci_low,ci_high,ci_level,ci_method,bootstrap_unit,n_events,n_runs,"
    "n_data,n_mc,numerator,denominator,p_value,effect_size,baseline_value,"
    "baseline_unc,delta_vs_baseline,delta_ci_low,delta_ci_high,truth_type,status,"
    "allowed_status_validated,source_report,source_script,source_data,source_config,"
    "source_manifest,figure_ids,table_ids,source_commit,link_validated,ci_status,"
    "blocked_by,supersedes,notes"
)


def ledger_text(**updates: str) -> str:
    row = {
        "claim_id": "CL-011",
        "chapter": "Pile-up",
        "section": "5",
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
        "n_events": "",
        "n_runs": "14",
        "n_data": "252266",
        "n_mc": "",
        "numerator": "",
        "denominator": "",
        "p_value": "",
        "effect_size": "",
        "baseline_value": "",
        "baseline_unc": "",
        "delta_vs_baseline": "",
        "delta_ci_low": "",
        "delta_ci_high": "",
        "truth_type": "data_measurement",
        "status": "DONE_DATA_ONLY",
        "allowed_status_validated": "NO",
        "source_report": "reports/1781000867.546870.5c124aaf/REPORT.md",
        "source_script": (
            "reports/1781000867.546870.5c124aaf/"
            "s10b_tau_eff_template_fit.py"
        ),
        "source_data": "reports/1781000867.546870.5c124aaf/result.json",
        "source_config": "",
        "source_manifest": "reports/1781000867.546870.5c124aaf/manifest.json",
        "figure_ids": "",
        "table_ids": "",
        "source_commit": "da9651c56ef6495ce9656d84b69b600daa6d8f86",
        "link_validated": "YES",
        "ci_status": "CI_AVAILABLE_RUN_BOOTSTRAP_METHOD_LIMITATIONS",
        "blocked_by": "BLK-S10B-001",
        "supersedes": "90 ns",
        "notes": (
            "This is a run-average estimand across 14 runs and 252266 selected pulses; "
            "it is not a detector-wide universal dead time. MV5 uses the value as an "
            "input rather than independently validating it."
        ),
    }
    row.update(updates)
    fields = next(csv.reader([HEADER]))
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(fields)
    writer.writerow([row[field] for field in fields])
    return output.getvalue()


VALUE_CELL = (
    "124.79018394263471 ns; run-bootstrap 95% CI "
    "[123.33094981246663, 126.35875117626817] ns"
)
CANONICAL_ROW = (
    "| τeff (effective live-time) | "
    + VALUE_CELL
    + " | — | — | data_measurement | **DONE_DATA_ONLY** |"
)
PILEUP_ROW = (
    "| τeff (effective live-time) | "
    + VALUE_CELL
    + " | **DONE_DATA_ONLY** |"
)
PILEUP_PROSE = (
    "The S10b run-average is based on 14 runs and 252266 selected pulses. "
    "The source reports a run-bootstrap 95% interval. This threshold- and "
    "selection-specific estimand is not a detector-wide universal dead time. "
    "MV5 uses the value as an input rather than independently validating it. "
    "Independent closure and a complete systematic model remain blocked by "
    "BLK-S10B-001."
)

CORRECT_WIKI = "\n".join([
    "# Wiki",
    "",
    "### Canonical Results Table",
    "",
    "| Claim | Current value | Stat. unc. | Syst. unc. | Truth type | Status |",
    "|---|---|---|---|---|---|",
    CANONICAL_ROW,
    "",
    "### Next section",
    "",
    "## 5. Pile-up Analysis",
    "",
    "| Observable | Value | Status |",
    "|---|---|---|",
    PILEUP_ROW,
    "",
    PILEUP_PROSE,
    "",
    "## 6. Other",
    "",
])


STALE_WIKI = """# Wiki

### Canonical Results Table

| Claim | Current value | Stat. unc. | Syst. unc. | Truth type | Status |
|---|---|---|---|---|---|
| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 | data + MC self-consistent | **VALIDATED** |

### Next section

## 5. Pile-up Analysis

> τeff remains validated.

| Observable | Value | Status |
|---|---|---|
| τeff (effective live-time) | 124.79 ns | **VALIDATED** |

The effective live-time estimate remains `124.79 ns`.

## 6. Other
"""


def write_inputs(tmp_path: Path, wiki: str, ledger: str | None = None) -> tuple[Path, Path]:
    wiki_path = tmp_path / "WIKI.md"
    ledger_path = tmp_path / "claim_ledger.csv"
    wiki_path.write_text(wiki, encoding="utf-8")
    ledger_path.write_text(ledger or ledger_text(), encoding="utf-8")
    return wiki_path, ledger_path


def test_correct_binding_validates(tmp_path: Path) -> None:
    wiki_path, ledger_path = write_inputs(tmp_path, CORRECT_WIKI)
    result = MODULE.audit(wiki_path, ledger_path)
    assert result["status"] == "VALIDATED"
    assert result["issues"] == []


def test_current_like_stale_wiki_fails_with_location_bound_findings(tmp_path: Path) -> None:
    wiki_path, ledger_path = write_inputs(tmp_path, STALE_WIKI)
    result = MODULE.audit(wiki_path, ledger_path)
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "FLAWED"
    assert "CANONICAL_ROW_STATUS_MISMATCH" in codes
    assert "CANONICAL_ROW_TRUTH_TYPE_MISMATCH" in codes
    assert "CANONICAL_ROW_UNSUPPORTED_COMPONENTS" in codes
    assert "PILEUP_ROW_STATUS_MISMATCH" in codes
    assert "STALE_TAU_EFF_PUBLIC_TEXT" in codes


def test_global_exact_tokens_do_not_rescue_stale_sections(tmp_path: Path) -> None:
    decoy = STALE_WIKI + "\n" + "\n".join(MODULE.REQUIRED_PILEUP_PHRASES)
    wiki_path, ledger_path = write_inputs(tmp_path, decoy)
    result = MODULE.audit(wiki_path, ledger_path)
    codes = {issue["code"] for issue in result["issues"]}
    assert "CANONICAL_ROW_STATUS_MISMATCH" in codes
    assert "PILEUP_ROW_STATUS_MISMATCH" in codes


def test_ledger_uncertainty_component_fails(tmp_path: Path) -> None:
    wiki_path, ledger_path = write_inputs(
        tmp_path,
        CORRECT_WIKI,
        ledger_text(stat_unc="0.5"),
    )
    result = MODULE.audit(wiki_path, ledger_path)
    assert any(
        issue["code"] == "UNSUPPORTED_UNCERTAINTY_COMPONENT"
        for issue in result["issues"]
    )


def test_duplicate_pileup_heading_is_controlled_input_error(tmp_path: Path) -> None:
    wiki_path, ledger_path = write_inputs(tmp_path, CORRECT_WIKI + "\n## 5. Pile-up Analysis\n")
    try:
        MODULE.audit(wiki_path, ledger_path)
    except MODULE.AuditInputError as exc:
        assert "expected one" in str(exc)
    else:
        raise AssertionError("duplicate heading should fail")


def test_cli_invalid_utf8_and_alias_fail_closed(tmp_path: Path) -> None:
    wiki_path, ledger_path = write_inputs(tmp_path, CORRECT_WIKI)
    wiki_path.write_bytes(b"# Wiki\n\xff")
    invalid = subprocess.run(
        [sys.executable, str(MODULE_PATH), str(wiki_path), str(ledger_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid.returncode == 2
    assert "not valid UTF-8" in invalid.stderr

    wiki_path.write_text(CORRECT_WIKI, encoding="utf-8")
    alias = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            str(wiki_path),
            str(ledger_path),
            "--output",
            str(wiki_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert alias.returncode == 2
    assert "must not alias" in alias.stderr


def test_cli_atomic_json_output(tmp_path: Path) -> None:
    wiki_path, ledger_path = write_inputs(tmp_path, CORRECT_WIKI)
    output = tmp_path / "result.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            str(wiki_path),
            str(ledger_path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "VALIDATED"
    assert not list(tmp_path.glob(".result.json.*"))
