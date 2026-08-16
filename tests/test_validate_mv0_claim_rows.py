from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "validate_mv0_claim_rows.py"
SPEC = importlib.util.spec_from_file_location("validate_mv0_claim_rows", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

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


def row(claim_id: str) -> dict[str, str]:
    common = {
        "claim_id": claim_id,
        "chapter": "Energy",
        "section": "7",
        "truth_type": "data_mc_calibration_proxy",
        "source_report": mod.REPORT_PATH,
        "source_script": mod.SCRIPT_PATH,
        "source_data": mod.DATA_PATH,
        "source_commit": mod.SOURCE_COMMIT,
        "link_validated": "YES",
        "blocked_by": "BLK-MV0-001",
    }
    if claim_id == "CL-013":
        common.update(
            {
                "claim_text": "Digitizer gain MV0 v2 median-matching estimate",
                "current_value": "92",
                "unit": "ADC/MeV",
                "syst_unc": "28",
                "ci_method": "systematic_envelope",
                "n_data": "579424",
                "n_mc": "321130",
                "baseline_value": "110",
                "delta_vs_baseline": "-18",
                "status": "GATED",
                "allowed_status_validated": "NO",
                "ci_status": "SYSTEMATIC_ENVELOPE_NOT_CONFIDENCE_INTERVAL",
                "supersedes": "110 ADC/MeV v1",
                "notes": (
                    "The 30% heuristic systematic envelope is not a confidence interval; "
                    "the producer/data manifest is absent, so this result is not authorized "
                    "as a precision calibration."
                ),
            }
        )
    else:
        common.update(
            {
                "claim_text": "MV0 B2 KS statistic at median-matched gain",
                "current_value": "0.1577",
                "unit": "dimensionless",
                "ci_method": "fixed_two_sample_KS_statistic",
                "n_data": "579424",
                "n_mc": "321130",
                "baseline_value": "0.1188",
                "delta_vs_baseline": "0.0389",
                "status": "TENSION",
                "allowed_status_validated": "YES",
                "ci_status": "NOT_APPLICABLE_FIXED_OUTPUT_P_VALUE_NOT_REPORTED",
                "notes": (
                    "This is a fixed source output; the p-value is not reported, and "
                    "selection-threshold closure is absent. It is not a calibrated "
                    "goodness-of-fit probability."
                ),
            }
        )
    return {field: common.get(field, "") for field in HEADER}


def ledger_text(rows: list[dict[str, str]]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


REPORT = """Gain = **92 ± 28 ADC/MeV**
KS optimal gain | 60 ADC/MeV (KS=0.119)
KS at gain=92 | 0.158
±30% on the gain
"""
CALIBRATION = json.dumps(
    {
        "calibration": {
            "gain_adc_per_mev": 92.0,
            "gain_systematic_unc_pct": 30,
            "ks_best": 0.1188,
            "ks_best_gain": 60.0,
            "ks_at_median_gain": 0.1577,
        },
        "data_net_amplitude_stats": {"B2": {"n": 579424}},
        "mc_b2_edep_stats_mev": {"n_tracks_with_B2_hit": 321130},
    }
)


def test_valid_rows_pass() -> None:
    result = mod.validate_texts(
        ledger_text([row("CL-013"), row("CL-014")]), REPORT, CALIBRATION
    )
    assert result["status"] == "VALIDATED"
    assert result["n_issues"] == 0


def test_wrong_gain_fails() -> None:
    cl013 = row("CL-013")
    cl013["current_value"] = "110"
    result = mod.validate_texts(
        ledger_text([cl013, row("CL-014")]), REPORT, CALIBRATION
    )
    assert result["status"] == "FLAWED"
    assert any(issue.get("field") == "current_value" for issue in result["issues"])


def test_missing_caveat_fails() -> None:
    cl014 = row("CL-014")
    cl014["notes"] = "fixed source output"
    result = mod.validate_texts(
        ledger_text([row("CL-013"), cl014]), REPORT, CALIBRATION
    )
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "MISSING_REQUIRED_CAVEAT" for issue in result["issues"])


def test_width_mismatch_fails_closed() -> None:
    parsed = list(
        csv.reader(io.StringIO(ledger_text([row("CL-013"), row("CL-014")])))
    )
    parsed[1] = parsed[1][:-1]
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows(parsed)
    try:
        mod.validate_texts(stream.getvalue(), REPORT, CALIBRATION)
    except mod.InputError as exc:
        assert "columns" in str(exc)
    else:
        raise AssertionError("expected InputError")


def test_cli_invalid_utf8_returns_two(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    report = tmp_path / "report.md"
    calibration = tmp_path / "calibration.json"
    ledger.write_bytes(b"\xff")
    report.write_text(REPORT, encoding="utf-8")
    calibration.write_text(CALIBRATION, encoding="utf-8")
    assert mod.main([str(ledger), str(report), str(calibration)]) == 2
