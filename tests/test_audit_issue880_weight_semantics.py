from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit.audit_issue880_weight_semantics import audit, main


CURRENT_LIKE_SOURCE = '''
import numpy as np

def wmean(x, w):
    sw = w.sum()
    return float(np.sum(w * x) / sw) if sw > 0 else float(x.mean())

def wmedian(x, w):
    sw = w.sum()
    if sw <= 0:
        return float(np.median(x))
    return 1.0

def wfrac(x, w, thr):
    sw = w.sum()
    return float(np.sum(w[x > thr]) / sw) if sw > 0 else float(np.mean(x > thr))

def wcorr(x, y, w):
    sw = w.sum()
    if sw <= 0:
        return float(np.corrcoef(x, y)[0, 1])
    return 0.0

def load_mc(pw):
    w_evt = np.asarray(pw, float)
    w_evt = np.where(np.isfinite(w_evt), w_evt, 1.0)
    return w_evt
'''

CURRENT_LIKE_RESULT = {
    "study": "issues879_880_887_mc_analysis",
    "issue_880_weight_audit": {
        "first_B_layer_mean_MeV": {
            "unweighted": 6.674567424757,
            "weighted": 2.134364334727324,
        },
        "deuteron_fraction_entering_B": {
            "unweighted": 0.5719111928400914,
            "weighted": 0.16606032425392264,
        },
        "bias_summary": {
            "first_B_layer_mean_rel_bias_pct": -68.02243203341332,
            "deuteron_fraction_abs_bias_pp": -40.585086858616876,
        },
        "note": "The fields show how much the legacy UNWEIGHTED summaries were off.",
    },
}


def _write_inputs(tmp_path: Path, source: str, payload: dict) -> tuple[Path, Path]:
    study = tmp_path / "study.py"
    result = tmp_path / "result.json"
    study.write_text(source, encoding="utf-8")
    result.write_text(json.dumps(payload), encoding="utf-8")
    return study, result


def test_current_like_inputs_fail_with_direction_and_weight_findings(tmp_path: Path) -> None:
    study, result = _write_inputs(tmp_path, CURRENT_LIKE_SOURCE, CURRENT_LIKE_RESULT)
    report = audit(study, result)
    codes = {item["code"] for item in report["findings"]}

    assert report["status"] == "FLAWED"
    assert "NONFINITE_WEIGHT_COERCED_TO_UNIT" in codes
    assert "INVALID_WEIGHT_FALLS_BACK_TO_UNWEIGHTED" in codes
    assert "RELATIVE_BIAS_DIRECTION_AMBIGUOUS" in codes
    assert "ABSOLUTE_BIAS_DIRECTION_AMBIGUOUS" in codes
    assert "PROSE_DIRECTION_CONFLICT" in codes
    assert "PROVENANCE_FIELD_MISSING" in codes

    calc = report["independent_recalculation"]
    assert calc["weighted_change_relative_to_unweighted_pct"] == pytest.approx(
        -68.02243203341332
    )
    assert calc["legacy_unweighted_overstatement_relative_to_weighted_pct"] == pytest.approx(
        212.7192164972955
    )
    assert calc["legacy_unweighted_minus_weighted_pp"] == pytest.approx(
        40.585086858616876
    )
    assert calc["legacy_deuteron_overstatement_relative_to_weighted_pct"] == pytest.approx(
        244.39966043037631
    )


def test_direction_explicit_strict_fixture_validates(tmp_path: Path) -> None:
    source = '''
import numpy as np

def validate_weights(w):
    w = np.asarray(w, float)
    if not np.all(np.isfinite(w)) or np.any(w < 0) or w.sum() <= 0:
        raise ValueError("invalid weights")
    return w
'''
    payload = {
        "root_sha256": "a" * 64,
        "producer_commit": "b" * 40,
        "generation_command": "python study.py --root input.root --out out",
        "weight_validation_policy": "FAIL_CLOSED_NONNEGATIVE_FIRST_PRIMARY",
        "issue_880_weight_audit": {
            "first_B_layer_mean_MeV": {"unweighted": 10.0, "weighted": 5.0},
            "deuteron_fraction_entering_B": {"unweighted": 0.6, "weighted": 0.2},
            "bias_summary": {
                "weighted_change_relative_to_unweighted_pct": -50.0,
                "legacy_unweighted_overstatement_relative_to_weighted_pct": 100.0,
                "legacy_unweighted_minus_weighted_pp": 40.0,
            },
            "note": (
                "Directional comparisons are explicit: weighted minus unweighted uses the "
                "unweighted denominator; legacy unweighted minus weighted uses the "
                "weighted baseline."
            ),
        },
    }
    study, result = _write_inputs(tmp_path, source, payload)
    report = audit(study, result)
    assert report["status"] == "VALIDATED"
    assert report["findings"] == []


def test_mismatched_retained_change_is_detected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(CURRENT_LIKE_RESULT))
    payload["issue_880_weight_audit"]["bias_summary"][
        "first_B_layer_mean_rel_bias_pct"
    ] = -67.0
    study, result = _write_inputs(tmp_path, CURRENT_LIKE_SOURCE, payload)
    report = audit(study, result)
    codes = {item["code"] for item in report["findings"]}
    assert "REPORTED_RELATIVE_CHANGE_MISMATCH" in codes


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    study, result = _write_inputs(tmp_path, CURRENT_LIKE_SOURCE, CURRENT_LIKE_RESULT)
    study.write_bytes(b"print('ok')\n\xff")
    report = audit(study, result)
    assert report["status"] == "INPUT_ERROR"
    assert report["error_type"] == "UnicodeDecodeError"


def test_cli_publishes_json_atomically_and_returns_one(tmp_path: Path) -> None:
    study, result = _write_inputs(tmp_path, CURRENT_LIKE_SOURCE, CURRENT_LIKE_RESULT)
    output = tmp_path / "audit.json"
    with pytest.raises(SystemExit) as exc:
        main(["--study", str(study), "--result", str(result), "--out", str(output)])
    assert exc.value.code == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "FLAWED"
    assert not list(tmp_path.glob(".audit.json.*.tmp"))


def test_cli_rejects_input_output_alias(tmp_path: Path) -> None:
    study, result = _write_inputs(tmp_path, CURRENT_LIKE_SOURCE, CURRENT_LIKE_RESULT)
    before = result.read_bytes()
    with pytest.raises(SystemExit) as exc:
        main(["--study", str(study), "--result", str(result), "--out", str(result)])
    assert exc.value.code == 2
    assert result.read_bytes() == before
