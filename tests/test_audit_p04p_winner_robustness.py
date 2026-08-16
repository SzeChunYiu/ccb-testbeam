from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audit.audit_p04p_winner_robustness import P04pAuditError, audit_payload


def method(
    name: str,
    coverage: float,
    coverage_ci: tuple[float, float],
    charge: float,
    timing: float,
    ece: float,
) -> dict:
    return {
        "method": name,
        "accepted_coverage": coverage,
        "accepted_coverage_ci95": list(coverage_ci),
        "accepted_charge_res68_frac": charge,
        "accepted_timing_abs68_ns": timing,
        "calibration_ece": ece,
    }


def current_like_payload() -> dict:
    return {
        "study": "P04p",
        "winner": "gradient_boosted_trees",
        "winner_selection": (
            "coverage>=0.50 then min accepted_charge_res68_frac, "
            "accepted_timing_abs68_ns, calibration_ece"
        ),
        "harm_methods": [
            method(
                "gradient_boosted_trees",
                0.5016432417313474,
                (0.4781032287979763, 0.5382552094265317),
                0.03902452880489024,
                0.039143681860957444,
                0.0750709805072009,
            ),
            method(
                "mlp",
                0.5470846194571808,
                (0.5225633159229767, 0.580955936618611),
                0.04055070702536622,
                0.04517760365138898,
                0.007440736549030646,
            ),
            method(
                "traditional_rule",
                0.7965177260331445,
                (0.7726672918889558, 0.823106967936089),
                0.07854122474166687,
                0.03807678647200362,
                0.13158170757289703,
            ),
            method(
                "shuffled_target_gbt",
                1.0,
                (1.0, 1.0),
                0.11166921405901398,
                0.07317504179325625,
                0.09800307334250893,
            ),
        ],
    }


def test_current_like_winner_changes_under_ci_gate() -> None:
    result = audit_payload(current_like_payload())
    assert result["status"] == "FLAWED"
    assert result["recomputed_point_estimate_winner"] == "gradient_boosted_trees"
    assert result["ci_lower_bound_winner"] == "mlp"
    assert not result["winner_stable_to_ci_lower_bound_gate"]
    assert {issue["code"] for issue in result["issues"]} == {
        "COVERAGE_GATE_UNCERTAINTY_POLICY_MISSING",
        "WINNER_CHANGES_UNDER_CI_LOWER_BOUND_GATE",
    }


def test_stable_preregistered_gate_validates() -> None:
    payload = current_like_payload()
    payload["winner"] = "mlp"
    payload["coverage_gate_uncertainty_policy"] = "LOWER_95_CI_AT_LEAST_THRESHOLD"
    payload["harm_methods"][0]["accepted_charge_res68_frac"] = 0.050
    payload["winner_selection"] = (
        "accepted_coverage_ci95 lower bound >=0.50 then min "
        "accepted_charge_res68_frac, accepted_timing_abs68_ns, calibration_ece"
    )
    result = audit_payload(payload)
    assert result["status"] == "VALIDATED"
    assert result["ci_lower_bound_winner"] == "mlp"
    assert result["recomputed_point_estimate_winner"] == "mlp"
    assert result["issues"] == []


def test_invalid_coverage_interval_is_rejected() -> None:
    payload = current_like_payload()
    payload["harm_methods"][0]["accepted_coverage_ci95"] = [0.60, 0.40]
    with pytest.raises(P04pAuditError, match="0 <= low <= point <= high <= 1"):
        audit_payload(payload)


def test_cli_writes_json_and_svg_and_returns_one(tmp_path: Path) -> None:
    source = tmp_path / "result.json"
    output = tmp_path / "audit.json"
    svg = tmp_path / "audit.svg"
    source.write_text(json.dumps(current_like_payload()) + "\n", encoding="utf-8")
    script = Path("tools/audit/audit_p04p_winner_robustness.py")
    completed = subprocess.run(
        [sys.executable, str(script), str(source), "--output", str(output), "--svg", str(svg)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "FLAWED"
    assert payload["result_json"]["snapshot_method"] == "SINGLE_READ_EXACT_BYTES"
    assert "P04p winner is not stable" in svg.read_text(encoding="utf-8")


def test_cli_invalid_utf8_returns_two(tmp_path: Path) -> None:
    source = tmp_path / "result.json"
    source.write_bytes(b"\xff\xfe")
    script = Path("tools/audit/audit_p04p_winner_robustness.py")
    completed = subprocess.run(
        [sys.executable, str(script), str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "not valid UTF-8" in completed.stderr
