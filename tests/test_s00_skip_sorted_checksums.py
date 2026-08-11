"""Tests for S00 write_checksums gate-aware behavior (#973)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "01_build_pulse_table_from_root.py"


def _load_s00():
    spec = importlib.util.spec_from_file_location("s00_checksums_lane08", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def s00():
    if not SCRIPT_PATH.exists():
        pytest.skip(f"{SCRIPT_PATH} not found")
    return _load_s00()


def test_skip_sorted_preserves_raw_hashes_and_records_missing_sorted(s00, tmp_path):
    raw_dir = tmp_path / "raw"
    sorted_dir = tmp_path / "sorted"
    raw_dir.mkdir()
    sorted_dir.mkdir()
    raw = raw_dir / "hrdb_run_0064.root"
    raw.write_bytes(b"raw-bytes-64")
    # sorted deliberately absent

    config = {
        "raw_root_dir": str(raw_dir),
        "sorted_b_dir": str(sorted_dir),
        "run_groups": {"sample_ii_calib": [64]},
    }
    out = tmp_path / "out"
    out.mkdir()
    df = s00.write_checksums(config, out, skip_sorted=True)
    assert (out / "input_sha256.csv").is_file()
    raw_rows = df[df["file"].astype(str).str.endswith("hrdb_run_0064.root")]
    assert len(raw_rows) == 1
    assert raw_rows.iloc[0]["present"] is True or raw_rows.iloc[0]["present"] == True
    assert isinstance(raw_rows.iloc[0]["sha256"], str) and len(raw_rows.iloc[0]["sha256"]) == 64
    sorted_rows = df[df["file"].astype(str).str.endswith("hrdb_run_0064-sorted.root")]
    assert len(sorted_rows) == 1
    assert sorted_rows.iloc[0]["present"] in (False, 0)
    assert sorted_rows.iloc[0]["missing_reason"] in {
        "skip_sorted",
        "not_consumed_skip_sorted",
    }
    # Must not raise / must not require --skip-sha256
    assert pd.isna(sorted_rows.iloc[0]["sha256"]) or sorted_rows.iloc[0]["sha256"] in ("", None)


def test_sorted_requested_but_absent_is_explicit_missing_not_crash(s00, tmp_path):
    raw_dir = tmp_path / "raw"
    sorted_dir = tmp_path / "sorted"
    raw_dir.mkdir()
    sorted_dir.mkdir()
    (raw_dir / "hrdb_run_0064.root").write_bytes(b"raw")
    config = {
        "raw_root_dir": str(raw_dir),
        "sorted_b_dir": str(sorted_dir),
        "run_groups": {"sample_ii_calib": [64]},
    }
    out = tmp_path / "out"
    out.mkdir()
    df = s00.write_checksums(config, out, skip_sorted=False)
    sorted_rows = df[df["file"].astype(str).str.endswith("-sorted.root")]
    assert len(sorted_rows) == 1
    assert sorted_rows.iloc[0]["present"] in (False, 0)
    assert "missing" in str(sorted_rows.iloc[0]["missing_reason"])
