from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "tools/audit/audit_real_data_cfd_single_stave_inference.py"
SPEC = importlib.util.spec_from_file_location("single_stave_audit", AUDIT_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _result(*, corrected: bool = False) -> dict:
    payload = {
        "sample_II": {
            "pulses_by_stave": {"B6": 17197, "B8": 10619},
            "pulse_shape": {
                "B6": {"samples_above_10pct_median": 8.0},
                "B8": {"samples_above_10pct_median": 10.0},
            },
            "best_sigma68": {
                "sigma68_ns": 0.8985129399585929,
                "ci68_ns": [0.8123935669551073, 1.0723601562332614],
                "tail_frac_gt5ns": 0.15889830508474576,
                "full_rms_ns": 9.69875913667869,
            },
        }
    }
    if corrected:
        payload["sample_II"]["single_stave_inference"] = {
            "authorized": False,
            "reason": "pair residual only; covariance and individual resolutions unresolved",
        }
    return payload


def test_current_like_contract_fails_with_expected_families():
    source = """
import numpy as np

def f(best):
    single = best['sigma68_ns'] / np.sqrt(2)
    return f'Single-stave estimate (pair / sqrt2), assume equal: {single}'
"""
    out = MOD.audit(source, _result())
    assert out["status"] == "FLAWED"
    codes = {item["code"] for item in out["findings"]}
    assert {
        "PAIR_SIGMA68_DIVIDED_BY_SQRT2",
        "PAIR_ONLY_RESULT_PROMOTED_TO_SINGLE_STAVE_CLAIM",
        "NO_COVARIANCE_OR_COMMON_MODE_MODEL",
        "NO_INDIVIDUAL_STAVE_DECONVOLUTION",
        "NON_GAUSSIAN_PAIR_WIDTH_USED_FOR_SQRT2_SCALING",
        "SINGLE_STAVE_UNCERTAINTY_NOT_PROPAGATED",
        "EQUAL_STAVE_ASSUMPTION_UNVALIDATED",
    } <= codes


def test_pair_only_corrected_contract_validates():
    source = """
def report(best):
    return f\"B6-B8 pair sigma68: {best['sigma68_ns']} ns\"
"""
    out = MOD.audit(source, _result(corrected=True))
    assert out["status"] == "VALIDATED"
    assert out["findings"] == []


def test_toy_controls_expose_non_general_scaling():
    controls = {row["case"]: row for row in MOD._toy_controls(n=120_000)}
    assert abs(controls["iid_normal"]["relative_error"]) < 0.02
    assert controls["iid_laplace"]["relative_error"] > 0.07
    assert controls["iid_heavy_tail_mixture"]["relative_error"] > 0.15
    assert controls["unequal_normal"]["relative_error"] > 0.45
    assert controls["equal_normal_rho_0p5"]["relative_error"] < -0.20


def test_cli_invalid_utf8_fails_closed(tmp_path):
    source = tmp_path / "source.py"
    source.write_bytes(b"\xff\xfe")
    result = tmp_path / "result.json"
    result.write_text(json.dumps(_result()), encoding="utf-8")
    output = tmp_path / "out.json"
    args = ["--source", str(source), "--result", str(result), "--output", str(output)]
    assert MOD.main(args) == 2
    assert not output.exists()


def test_cli_rejects_destructive_alias(tmp_path):
    source = _write(tmp_path / "source.py", "x = 1\n")
    result = tmp_path / "result.json"
    result.write_text(json.dumps(_result(corrected=True)), encoding="utf-8")
    with pytest.raises(SystemExit):
        MOD.main(["--source", str(source), "--result", str(result), "--output", str(source)])


def test_atomic_publication_preserves_previous_target(tmp_path, monkeypatch):
    target = tmp_path / "out.json"
    target.write_text("previous\n", encoding="utf-8")
    real_replace = os.replace

    def fail_replace(src, dst):
        if Path(dst) == target:
            raise OSError("injected")
        return real_replace(src, dst)

    monkeypatch.setattr(MOD.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        MOD._atomic_json(target, {"x": 1})
    assert target.read_text(encoding="utf-8") == "previous\n"
    assert not list(tmp_path.glob(f".{target.name}.*.tmp"))
