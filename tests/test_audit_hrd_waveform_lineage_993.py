from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "audit_hrd_waveform_lineage_993.py"
spec = importlib.util.spec_from_file_location("audit_hrd_waveform_lineage_993", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_build_lineage_verdict_distinct_when_only_16_passes():
    censuses = [
        mod.RunCensus(
            run=31,
            path="x",
            events_scanned=10,
            length_histogram={"128": 10},
            malformed_events=0,
            contract_8x16_pass=True,
            contract_8x18_pass=False,
        )
    ]
    hypotheses = mod.falsify_transform_hypotheses(censuses, [{"run": 31, "sha256": "abc"}])
    verdict = mod.build_lineage_verdict(hypotheses, censuses)
    assert verdict["verdict"] == "DISTINCT_SCHEMAS"
    assert verdict["authorising_waveform_schema_for_paper_amplitude_timing"] == "hrd_raw_8x16_v1"
    assert verdict["historical_18_sample_timing_authorising_for_16_sample_raw"] is False


def test_laptop_and_lunarc_run31_reference_hashes_differ():
    hypotheses = mod.falsify_transform_hypotheses([], [{"run": 31, "sha256": "0986c826deadbeef"}])
    row = hypotheses["identical_byte_stream_as_laptop_root"]
    assert row["accepted"] is False
    assert row["observed"]["equal"] is False


def test_audit_writes_manifest_on_synthetic_raw(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "out"
    config = tmp_path / "cfg.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "run_groups": {
                    "sample_i_calib": [31],
                }
            }
        ),
        encoding="utf-8",
    )
    canon = tmp_path / "canon.csv"
    canon.write_text(
        "run,group,eventno,evt,stave,channel,baseline_adc,amplitude_adc,peak_sample,area_adc_samples\n"
        "31,sample_i_calib,1,1,B2,0,10.0,100.0,5,1000.0\n",
        encoding="utf-8",
    )

    try:
        import uproot
    except ImportError:
        pytest.skip("uproot required")

    path = raw_dir / "hrdb_run_0031.root"
    ch0 = np.linspace(0, 15, 16)
    wf = np.tile(ch0, 8).astype(np.float64)
    wf[0:4] = [10, 10, 10, 10]
    wf[0::16] = wf[0::16] + np.array([0, 0, 0, 0, 0, 120, 0, 0])
    with uproot.recreate(path) as f:
        f["h101"] = {
            "EVENTNO": np.array([1], dtype=np.int64),
            "HRDv": [wf.tolist()],
        }

    manifest = mod.audit(
        raw_dir=raw_dir,
        config_path=config,
        canon_path=canon,
        out_dir=out_dir,
        event_sample_size=1,
        seed=993,
    )
    assert manifest["verdict"]["verdict"] == "DISTINCT_SCHEMAS"
    assert (out_dir / "manifest.json").is_file()
    assert (out_dir / "validation.json").is_file()
    validation = json.loads((out_dir / "validation.json").read_text())
    assert validation["verdict"] == "DISTINCT_SCHEMAS"
    assert validation["timing_18_sample_non_authorising"] is True
