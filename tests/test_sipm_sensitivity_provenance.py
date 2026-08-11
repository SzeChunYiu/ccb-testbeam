"""Tests for SiPM sensitivity provenance gate (#982) and related helpers."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "scripts" / "single_stave" / "sipm_sensitivity.py"


def _load():
    spec = importlib.util.spec_from_file_location("sipm_sensitivity", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["sipm_sensitivity"] = mod
    spec.loader.exec_module(mod)
    return mod


def _meta(digitizer: dict) -> dict:
    return {
        "schema": "ccb-stave-run-meta/1",
        "digitizer": {
            "validation_status": "OK",
            "digitizer_config_sha256": "abc123",
            "ccb_sipm_core_commit": "deadbeef",
            "adc_bits": 12,
            "baseline_adc": 200.0,
            **digitizer,
        },
    }


def test_adc_clip_from_metadata():
    mod = _load()
    assert mod.adc_clip_from_digitizer({"adc_bits": 12, "baseline_adc": 200}) == 3895.0
    assert mod.adc_clip_from_digitizer({"adc_bits": 14, "baseline_adc": 100}) == 16283.0


def test_requested_matches_effective_ok(tmp_path: Path):
    mod = _load()
    root = tmp_path / "crosstalk=0.root"
    root.write_bytes(b"dummy")
    meta = _meta({"prompt_crosstalk_probability": 0.0, "number_of_cells": 3600})
    (tmp_path / "crosstalk=0.root.meta.json").write_text(json.dumps(meta))
    loaded = mod.load_sidecar(root)
    row = mod.assert_requested_matches_effective("crosstalk", "0", loaded)
    assert row["effective"] == 0.0
    assert row["adc_clip"] == 3895.0


def test_filename_zero_but_metadata_default_fails(tmp_path: Path):
    mod = _load()
    root = tmp_path / "crosstalk=0.root"
    root.write_bytes(b"dummy")
    meta = _meta({"prompt_crosstalk_probability": 0.03})
    (tmp_path / "crosstalk=0.root.meta.json").write_text(json.dumps(meta))
    loaded = mod.load_sidecar(root)
    with pytest.raises(mod.ProvenanceError, match="!="):
        mod.assert_requested_matches_effective("crosstalk", "0", loaded)


def test_missing_sidecar_fails(tmp_path: Path):
    mod = _load()
    root = tmp_path / "sipm_n_cells=3600.root"
    root.write_bytes(b"dummy")
    with pytest.raises(mod.ProvenanceError, match="missing sidecar"):
        mod.load_sidecar(root)


def test_sipm_n_cells_effective_match():
    mod = _load()
    meta = _meta({"number_of_cells": 1600})
    row = mod.assert_requested_matches_effective("sipm_n_cells", "1600", meta)
    assert row["effective"] == 1600
