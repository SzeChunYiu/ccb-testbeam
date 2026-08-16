from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "validate_key_set_closure.py"
spec = importlib.util.spec_from_file_location("validate_key_set_closure", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def df(keys):
    return pd.DataFrame(keys, columns=["run", "evt"])


def test_equal_reordered_unique_key_sets_pass():
    left = df([(1, 1), (1, 2), (2, 1)])
    right = df([(2, 1), (1, 2), (1, 1)])
    result = mod.audit_key_set_closure(left, right, keys=["run", "evt"])
    assert result["exact_key_set"] is True
    assert result["matched_unique_keys"] == 3


def test_partial_overlap_fails_and_counts_both_sides():
    result = mod.audit_key_set_closure(
        df([(1, 1), (1, 2)]), df([(1, 2), (1, 3)]), keys=["run", "evt"]
    )
    assert result["exact_key_set"] is False
    assert result["matched_unique_keys"] == 1
    assert result["left_only_unique_keys"] == 1
    assert result["right_only_unique_keys"] == 1


def test_disjoint_unique_sets_fail():
    result = mod.audit_key_set_closure(df([(1, 1)]), df([(2, 2)]), keys=["run", "evt"])
    assert not result["exact_key_set"]
    assert result["matched_unique_keys"] == 0


def test_duplicate_key_rows_fail():
    result = mod.audit_key_set_closure(
        df([(1, 1), (1, 1)]), df([(1, 1)]), keys=["run", "evt"]
    )
    assert not result["exact_key_set"]
    assert result["left_duplicate_key_rows"] == 2


def test_null_key_rows_fail():
    left = pd.DataFrame({"run": [1, 1], "evt": [1.0, np.nan]})
    right = pd.DataFrame({"run": [1, 1], "evt": [1.0, 2.0]})
    result = mod.audit_key_set_closure(left, right, keys=["run", "evt"])
    assert not result["exact_key_set"]
    assert result["left_null_key_rows"] == 1


def test_dtype_mismatch_fails_closed_by_default():
    left = pd.DataFrame({"run": [1], "evt": [1]})
    right = pd.DataFrame({"run": ["1"], "evt": ["1"]})
    result = mod.audit_key_set_closure(left, right, keys=["run", "evt"])
    assert result["status"] == "KEY_DTYPE_MISMATCH"
    assert not result["exact_key_set"]


def test_missing_key_column_is_controlled_error():
    with pytest.raises(ValueError, match="right missing key columns"):
        mod.audit_key_set_closure(
            pd.DataFrame({"run": [1], "evt": [1]}),
            pd.DataFrame({"run": [1]}),
            keys=["run", "evt"],
        )
