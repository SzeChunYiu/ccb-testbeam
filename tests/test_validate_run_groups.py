from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "validate_run_groups.py"
spec = importlib.util.spec_from_file_location("validate_run_groups", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_disjoint_groups_pass():
    result = mod.validate_exclusive_run_groups(
        {"sample_i": [31, 32], "calibration": [61], "analysis": [59, 60, 62, 63]}
    )
    assert result["pass"] is True
    assert result["overlapping_run_roles"] == {}


def test_calibration_analysis_overlap_fails():
    result = mod.validate_exclusive_run_groups(
        {"calibration": [61], "analysis": [59, 60, 61, 62]}
    )
    assert result["pass"] is False
    assert result["overlapping_run_roles"]["61"] == ["calibration", "analysis"]


def test_duplicate_inside_one_group_fails():
    result = mod.validate_exclusive_run_groups({"analysis": [59, 59, 60]})
    assert not result["pass"]
    assert result["duplicate_within_group"] == {"analysis": [59]}


def test_can_validate_only_declared_exclusive_roles():
    result = mod.validate_exclusive_run_groups(
        {"all_sample_ii": [59, 60, 61], "calibration": [61], "analysis": [59, 60]},
        exclusive_groups=["calibration", "analysis"],
    )
    assert result["pass"]


def test_missing_requested_group_is_error():
    with pytest.raises(ValueError, match="not present"):
        mod.validate_exclusive_run_groups(
            {"analysis": [59]}, exclusive_groups=["analysis", "calibration"]
        )


def test_negative_or_noninteger_run_rejected():
    with pytest.raises(ValueError, match="negative"):
        mod.validate_exclusive_run_groups({"analysis": [-1]})
    with pytest.raises(ValueError, match="non-integer"):
        mod.validate_exclusive_run_groups({"analysis": ["run59"]})
