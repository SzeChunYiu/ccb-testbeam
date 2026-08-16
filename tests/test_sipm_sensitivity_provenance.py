"""Tests for SiPM sensitivity provenance gate (#982/#977) and related helpers."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "scripts" / "single_stave" / "sipm_sensitivity.py"
EXPECTED_CORE = "3627dc87137a9f33f511a755671414b11853c0a0"
OTHER_CORE = "f" * 40


def _load():
    spec = importlib.util.spec_from_file_location("sipm_sensitivity", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["sipm_sensitivity"] = mod
    spec.loader.exec_module(mod)
    return mod


def _meta(digitizer: dict) -> dict:
    return {
        "schema": "ccb-stave-run-meta/2",
        "digitizer": {
            "validation_status": "OK",
            "digitizer_config_sha256": "abc123",
            "ccb_sipm_core_commit": EXPECTED_CORE,
            "adc_bits": 12,
            "baseline_adc": 200.0,
            **digitizer,
        },
    }


def _write_point(tmp_path: Path, name: str, meta: dict) -> Path:
    root = tmp_path / name
    root.write_bytes(b"dummy")
    (tmp_path / f"{name}.meta.json").write_text(json.dumps(meta))
    return root


def test_adc_clip_from_metadata():
    mod = _load()
    assert mod.adc_clip_from_digitizer({"adc_bits": 12, "baseline_adc": 200}) == 3895.0
    assert mod.adc_clip_from_digitizer({"adc_bits": 14, "baseline_adc": 100}) == 16283.0


def test_requested_matches_effective_ok(tmp_path: Path):
    mod = _load()
    root = _write_point(
        tmp_path,
        "crosstalk=0.root",
        _meta({"prompt_crosstalk_probability": 0.0, "number_of_cells": 3600}),
    )
    loaded = mod.load_sidecar(root)
    row = mod.assert_requested_matches_effective("crosstalk", "0", loaded)
    assert row["effective"] == 0.0
    assert row["adc_clip"] == 3895.0
    assert row["ccb_sipm_core_commit"] == EXPECTED_CORE


def test_filename_zero_but_metadata_default_fails(tmp_path: Path):
    mod = _load()
    root = _write_point(
        tmp_path,
        "crosstalk=0.root",
        _meta({"prompt_crosstalk_probability": 0.03}),
    )
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


def test_missing_core_sha_fails_closed(tmp_path: Path):
    mod = _load()
    root = _write_point(
        tmp_path,
        "crosstalk=0.root",
        _meta({"prompt_crosstalk_probability": 0.0, "ccb_sipm_core_commit": None}),
    )
    with pytest.raises(mod.ProvenanceError, match="ccb_sipm_core_commit missing or invalid"):
        mod.load_sidecar(root)


def test_short_core_sha_fails_closed_even_with_ok_status_and_digest(tmp_path: Path):
    mod = _load()
    root = _write_point(
        tmp_path,
        "crosstalk=0.root",
        _meta({"prompt_crosstalk_probability": 0.0, "ccb_sipm_core_commit": "deadbeef"}),
    )
    with pytest.raises(mod.ProvenanceError, match="ccb_sipm_core_commit missing or invalid"):
        mod.load_sidecar(root)


def test_expected_core_sha_mismatch_fails_closed(tmp_path: Path):
    mod = _load()
    root = _write_point(
        tmp_path,
        "crosstalk=0.root",
        _meta({"prompt_crosstalk_probability": 0.0, "ccb_sipm_core_commit": OTHER_CORE}),
    )
    with pytest.raises(mod.ProvenanceError, match="!= expected"):
        mod.load_sidecar(root, expected_core_sha=EXPECTED_CORE)


def test_expected_core_sha_exact_match_passes(tmp_path: Path):
    mod = _load()
    root = _write_point(
        tmp_path,
        "crosstalk=0.root",
        _meta({"prompt_crosstalk_probability": 0.0}),
    )
    loaded = mod.load_sidecar(root, expected_core_sha=EXPECTED_CORE)
    assert loaded["digitizer"]["ccb_sipm_core_commit"] == EXPECTED_CORE


def test_collect_knob_rejects_mixed_core_revisions(tmp_path: Path):
    mod = _load()
    _write_point(
        tmp_path,
        "crosstalk=0.root",
        _meta({"prompt_crosstalk_probability": 0.0}),
    )
    _write_point(
        tmp_path,
        "crosstalk=1.root",
        _meta({"prompt_crosstalk_probability": 1.0, "ccb_sipm_core_commit": OTHER_CORE}),
    )
    mod.read_point = lambda _root, adc_clip: {"adc_clip": adc_clip, "n_events": 1}
    with pytest.raises(mod.ProvenanceError, match="mixed ccb_sipm_core_commit"):
        mod.collect_knob(tmp_path)


def test_collect_knob_records_exact_core_identity(tmp_path: Path):
    mod = _load()
    _write_point(
        tmp_path,
        "crosstalk=0.root",
        _meta({"prompt_crosstalk_probability": 0.0}),
    )
    mod.read_point = lambda _root, adc_clip: {"adc_clip": adc_clip, "n_events": 1}
    _values, _stats, _labels, rows = mod.collect_knob(
        tmp_path, expected_core_sha=EXPECTED_CORE
    )
    assert rows[0]["ccb_sipm_core_commit"] == EXPECTED_CORE
    assert rows[0]["core_identity_status"] == "EXACT_40HEX_CAMPAIGN_CONSISTENT"
