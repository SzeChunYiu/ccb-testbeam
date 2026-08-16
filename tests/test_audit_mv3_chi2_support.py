from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "audit_mv3_chi2_support.py"
SPEC = importlib.util.spec_from_file_location("audit_mv3_chi2_support", MODULE_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

CURRENT = '''
import numpy as np
STAVES = ("B2", "B4", "B6", "B8")
class ContractError(RuntimeError):
    pass
def _chi2(mc_frac, data_counts):
    mc = np.asarray([mc_frac.get(stave, 0.0) for stave in STAVES], dtype=float)
    observed = np.asarray([data_counts.get(stave, 0.0) for stave in STAVES], dtype=float)
    if not np.all(np.isfinite(mc)) or not np.all(np.isfinite(observed)):
        raise ContractError("NONFINITE_CHI2_INPUT")
    if np.any(mc < 0.0) or np.any(observed < 0.0):
        raise ContractError("NEGATIVE_CHI2_INPUT")
    expected = mc * observed.sum()
    positive = expected > 0.0
    ndf = int(positive.sum()) - 1
    if ndf <= 0:
        raise ContractError("NONPOSITIVE_CHI2_NDF")
    chi2 = float(np.sum((observed[positive] - expected[positive]) ** 2 / expected[positive]))
    return chi2, ndf, chi2 / ndf
'''

CORRECTED = '''
import math
import numpy as np
STAVES = ("B2", "B4", "B6", "B8")
class ContractError(RuntimeError):
    pass
def _chi2(mc_frac, data_counts):
    mc = np.asarray([mc_frac.get(stave, 0.0) for stave in STAVES], dtype=float)
    observed = np.asarray([data_counts.get(stave, 0.0) for stave in STAVES], dtype=float)
    if not np.all(np.isfinite(mc)) or not np.all(np.isfinite(observed)):
        raise ContractError("NONFINITE_CHI2_INPUT")
    if np.any(mc < 0.0) or np.any(observed < 0.0):
        raise ContractError("NEGATIVE_CHI2_INPUT")
    total = math.fsum(float(value) for value in mc)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ContractError(f"CHI2_PROFILE_NOT_NORMALIZED:sum={total}")
    observed_total = float(observed.sum())
    if observed_total <= 0.0:
        raise ContractError("NONPOSITIVE_CHI2_OBSERVED_TOTAL")
    expected = mc * observed_total
    if np.any((expected == 0.0) & (observed > 0.0)):
        raise ContractError("CHI2_OBSERVED_OUTSIDE_MODEL_SUPPORT")
    positive = expected > 0.0
    ndf = int(positive.sum()) - 1
    if ndf <= 0:
        raise ContractError("NONPOSITIVE_CHI2_NDF")
    chi2 = float(np.sum((observed[positive] - expected[positive]) ** 2 / expected[positive]))
    return chi2, ndf, chi2 / ndf
'''


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "producer.py"
    path.write_text(text, encoding="utf-8")
    return path


def test_current_contract_is_flawed(tmp_path):
    result = MOD.audit(_write(tmp_path, CURRENT))
    assert result["status"] == "FLAWED"
    codes = {finding["code"] for finding in result["findings"]}
    assert "OBSERVED_MASS_OUTSIDE_MODEL_SUPPORT_NOT_REJECTED" in codes
    assert "NONUNIT_MODEL_PROFILE_NOT_REJECTED" in codes
    outside = result["controls"]["positive_observed_zero_expected"]
    assert outside == {
        "outcome": "RETURNED",
        "chi2": 1.0,
        "ndf": 1,
        "chi2_per_ndf": 1.0,
    }


def test_corrected_contract_validates(tmp_path):
    result = MOD.audit(_write(tmp_path, CORRECTED))
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0
    assert result["controls"]["valid_four_bin"]["ndf"] == 3
    assert result["controls"]["zero_expected_zero_observed"]["ndf"] == 1


def test_nonunit_profile_rejection_is_specific(tmp_path):
    result = MOD.audit(_write(tmp_path, CORRECTED))
    control = result["controls"]["nonunit_model_profile"]
    assert control["outcome"] == "RAISED"
    assert "CHI2_PROFILE_NOT_NORMALIZED" in control["message"]


def test_invalid_utf8_is_controlled(tmp_path):
    source = tmp_path / "producer.py"
    source.write_bytes(b"class ContractError(Exception):\n\xff")
    output = tmp_path / "audit.json"
    assert MOD.main(["--source", str(source), "--output", str(output)]) == 2
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "INPUT_ERROR"
    assert "INVALID_UTF8" in result["findings"][0]["detail"]


def test_output_alias_is_rejected_without_overwrite(tmp_path):
    source = _write(tmp_path, CURRENT)
    before = source.read_bytes()
    assert MOD.main(["--source", str(source), "--output", str(source)]) == 2
    assert source.read_bytes() == before


def test_atomic_json_publication(tmp_path):
    source = _write(tmp_path, CURRENT)
    output = tmp_path / "nested" / "audit.json"
    assert MOD.main(["--source", str(source), "--output", str(output)]) == 1
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["source"]["bytes"] == len(CURRENT.encode("utf-8"))
    assert not list(output.parent.glob(".*.tmp"))
