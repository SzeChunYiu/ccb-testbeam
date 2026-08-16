from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "audit_mv3_selection_claim.py"
SPEC = importlib.util.spec_from_file_location("audit_mv3_selection_claim", MODULE_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

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


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def ledger_text(*, duplicate: bool = False) -> str:
    row = {key: "" for key in HEADER}
    row.update({
        "claim_id": "CL-021",
        "truth_type": "legacy_data_mc_profile_diagnostic",
        "status": "FLAWED",
        "blocked_by": "BLK-MV3-LEGACY-001",
    })
    lines = [",".join(HEADER), ",".join(row[key] for key in HEADER)]
    if duplicate:
        lines.append(",".join(row[key] for key in HEADER))
    return "\n".join(lines) + "\n"


def base_summary() -> dict:
    return {
        "verdict": "PARTIALLY RESOLVED (selection-matched, residual remains)",
        "chi2_improvement_factor": 16.602672795596263,
        "mc": {
            "unselected": {
                "stop_depth_counts": {
                    "B2": 106603, "B4": 40957, "B6": 28843, "B8": 55122
                },
                "stop_depth_frac": {
                    "B2": 0.4604383975812547,
                    "B4": 0.17690098261526832,
                    "B6": 0.12457833927221683,
                    "B8": 0.23808228053126013,
                },
            },
            "sample_i": {
                "stop_depth_counts": {
                    "B2": 55321, "B4": 3838, "B6": 1303, "B8": 3351
                },
                "stop_depth_frac": {
                    "B2": 0.8669236675912432,
                    "B4": 0.06014448466613386,
                    "B6": 0.02041903687336436,
                    "B8": 0.052512810869258617,
                },
            },
        },
        "data": {
            "all": {
                "stop_depth_counts": {
                    "B2": 326324, "B4": 19661, "B6": 11787, "B8": 7166
                },
                "stop_depth_frac": {
                    "B2": 0.8941902460143915,
                    "B4": 0.05387490477834591,
                    "B6": 0.03229863702875557,
                    "B8": 0.019636212178507036,
                },
            },
            "sample_i": {
                "stop_depth_counts": {
                    "B2": 270219, "B4": 8884, "B6": 4596, "B8": 2466
                },
                "stop_depth_frac": {
                    "B2": 0.9442769031852253,
                    "B4": 0.031045026470742403,
                    "B6": 0.016060664302063495,
                    "B8": 0.008617406041968794,
                },
            },
        },
    }


def snapshots(tmp_path: Path, *, corrected: bool = False):
    summary = base_summary()
    if corrected:
        summary.update({
            "verdict": "FLAWED_PENDING_WEIGHTED_RERUN",
            "chi2_improvement_factor": 16.11463523958161,
            "comparison_policy": "SAME_DATA_TARGET_FOR_SELECTION_ABLATION",
            "weighting": {
                "primaryweight_applied": True,
                "sum_w": 100.0,
                "sum_w2": 250.0,
                "effective_sample_size": 40.0,
            },
            "provenance": {
                "mc_sha256": "a" * 64,
                "data_pulse_sha256": "b" * 64,
                "script_sha256": "c" * 64,
                "source_commit": "d" * 40,
                "command": "python scripts/studies/mv3_selection_matched.py ...",
            },
            "sensitivity": {
                "gain": {},
                "threshold_adc": {},
                "coinc_ns": {},
                "weighting": {},
            },
            "uncertainty": {"mc_data_covariance_evaluated": True},
        })
        script = """from ccb_mc_validation.truth.pdg import is_charged
charged = [is_charged(p) for p in pd]
primaryweight_applied = True
weighted_stop_depth_counts = {}
stop_depth_weight_sum = 0.0
"""
        report = (
            "Status: FLAWED pending a content-addressed weighted rerun. "
            "The historical unweighted profile is sensitivity only; no shape-match claim."
        )
    else:
        script = """PrimaryWeight = ch['PrimaryWeight']
w_evt = float(pw[0]) if ok else 1.0
charged = [pdg_charge(int(p)) >= 1 for p in pd]
stop_depth_counts[depth] += 1
"""
        report = (
            "Events are unweighted; PrimaryWeight must NOT be used. "
            "There is NO physical differential cross-section weighting. "
            "The gap is gone and the shape matches."
        )
    paths = {
        "script": write(tmp_path / "script.py", script),
        "report": write(tmp_path / "REPORT.md", report),
        "summary": write(tmp_path / "summary.json", json.dumps(summary)),
        "ledger": write(tmp_path / "ledger.csv", ledger_text()),
        "weight": write(
            tmp_path / "weight.md",
            (
                "PrimaryWeight stores the cross-section factor; downstream "
                "unweighted truth results are not physical."
            ),
        ),
        "pdg": write(
            tmp_path / "pdg.py",
            "def is_charged(pdg):\n    return abs(pdg_charge(int(pdg))) > 0.5\n",
        ),
    }
    return {name: MOD._snapshot(path) for name, path in paths.items()}


def run_audit(snaps):
    return MOD.audit(
        script=snaps["script"],
        report=snaps["report"],
        summary=snaps["summary"],
        ledger=snaps["ledger"],
        weight_contract=snaps["weight"],
        pdg_helper=snaps["pdg"],
    )


def test_current_like_contract_fails_closed(tmp_path):
    result = run_audit(snapshots(tmp_path))
    assert result["status"] == "FLAWED"
    codes = {finding["code"] for finding in result["findings"]}
    assert "PRIMARY_WEIGHT_READ_BUT_NOT_APPLIED" in codes
    assert "POSITIVE_CHARGE_ONLY_MASK" in codes
    assert "VERDICT_OUTRUNS_CANONICAL_LEDGER" in codes
    assert "SHAPE_MATCH_CLAIM_WITH_REJECTED_CHI2" in codes
    residual = result["independent_calculations"][
        "sample_i_b2_residual_percentage_points"
    ]
    assert residual == pytest.approx(7.73532355939821)


def test_corrected_contract_validates(tmp_path):
    result = run_audit(snapshots(tmp_path, corrected=True))
    assert result["status"] == "VALIDATED"
    assert result["findings"] == []


def test_count_fraction_mutation_is_input_error(tmp_path):
    snaps = snapshots(tmp_path, corrected=True)
    summary_path = Path(snaps["summary"].path)
    data = json.loads(summary_path.read_text())
    data["mc"]["sample_i"]["stop_depth_frac"]["B2"] = 0.8
    summary_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(MOD.AuditInputError, match="COUNT_FRACTION_MISMATCH"):
        MOD.audit(
            script=snaps["script"],
            report=snaps["report"],
            summary=MOD._snapshot(summary_path),
            ledger=snaps["ledger"],
            weight_contract=snaps["weight"],
            pdg_helper=snaps["pdg"],
        )


def test_duplicate_cl021_is_rejected(tmp_path):
    snaps = snapshots(tmp_path, corrected=True)
    ledger_path = Path(snaps["ledger"].path)
    ledger_path.write_text(ledger_text(duplicate=True), encoding="utf-8")
    with pytest.raises(MOD.AuditInputError, match="CL021_CARDINALITY:2"):
        MOD._read_cl021(MOD._snapshot(ledger_path))


def test_invalid_utf8_returns_controlled_status(tmp_path, capsys):
    paths = snapshots(tmp_path, corrected=True)
    script = Path(paths["script"].path)
    script.write_bytes(b"ok\xffbad")
    status = MOD.main([
        "--script", str(script),
        "--report", paths["report"].path,
        "--summary", paths["summary"].path,
        "--ledger", paths["ledger"].path,
        "--weight-contract", paths["weight"].path,
        "--pdg-helper", paths["pdg"].path,
    ])
    assert status == 2
    assert "INVALID_UTF8" in capsys.readouterr().out


def test_output_alias_is_rejected(tmp_path, capsys):
    paths = snapshots(tmp_path, corrected=True)
    status = MOD.main([
        "--script", paths["script"].path,
        "--report", paths["report"].path,
        "--summary", paths["summary"].path,
        "--ledger", paths["ledger"].path,
        "--weight-contract", paths["weight"].path,
        "--pdg-helper", paths["pdg"].path,
        "--out", paths["summary"].path,
    ])
    assert status == 2
    assert "OUTPUT_ALIASES_INPUT" in capsys.readouterr().out


def test_atomic_json_publication(tmp_path):
    paths = snapshots(tmp_path, corrected=True)
    out = tmp_path / "nested" / "audit.json"
    status = MOD.main([
        "--script", paths["script"].path,
        "--report", paths["report"].path,
        "--summary", paths["summary"].path,
        "--ledger", paths["ledger"].path,
        "--weight-contract", paths["weight"].path,
        "--pdg-helper", paths["pdg"].path,
        "--out", str(out),
    ])
    assert status == 0
    assert json.loads(out.read_text())["status"] == "VALIDATED"
    assert list(out.parent.glob(f".{out.name}.*.tmp")) == []
