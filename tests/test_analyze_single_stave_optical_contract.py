from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "single_stave"
    / "analyze_single_stave.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("analyze_single_stave", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _current_frame(n: int = 60) -> pd.DataFrame:
    event = np.arange(n)
    scint = 10 + (event % 3)
    wls = 5 + (event % 2)
    cerenkov = event % 2
    total = scint + wls + cerenkov
    arrivals = scint + 1
    return pd.DataFrame(
        {
            "run_id": ["run-current"] * n,
            "event_id": event,
            "particle_pdg": [2212] * n,
            "kinetic_energy_MeV": [100.0] * n,
            "edep_scint_raw_MeV": (10.0 + event / 10.0) * 1.05,
            "edep_scint_MeV": 10.0 + event / 10.0,
            "n_scint_generated": scint,
            "n_wls_generated": wls,
            "n_cerenkov_generated": cerenkov,
            "n_optical_generated_total": total,
            "n_end_selected": arrivals,
            "n_detected_pe": np.minimum(arrivals, 4 + (event % 5)),
        }
    )


def _legacy_frame(n: int = 60) -> pd.DataFrame:
    event = np.arange(n)
    generated = 20 + (event % 4)
    return pd.DataFrame(
        {
            "run_id": ["run-legacy"] * n,
            "event_id": event,
            "particle_pdg": [2212] * n,
            "kinetic_energy_MeV": [100.0] * n,
            "edep_scint_raw_MeV": (8.0 + event / 10.0) * 1.05,
            "edep_scint_MeV": 8.0 + event / 10.0,
            "n_scint_generated": generated,
            "n_end_selected": generated - 3,
            "n_detected_pe": generated - 8,
        }
    )


def test_current_contract_accepts_wls_inclusive_arrival_bound():
    mod = _load()
    raw = _current_frame()
    assert (raw["n_end_selected"] > raw["n_scint_generated"]).all()
    normalized = mod.normalize_schema(raw)
    report = mod.validate_physics(normalized)
    assert report["passed"] is True
    assert report["optical_generation_contract"] == "CURRENT_COMPONENT_SUM"
    assert report["generated_optical_denominator"] == "n_optical_generated_total"
    assert report["optical_bookkeeping"]["components"]["n_wls_generated"]["sum"] > 0


def test_collection_efficiency_uses_total_not_scintillation_only():
    mod = _load()
    normalized = mod.normalize_schema(_current_frame())
    efficiency = mod.collection_efficiency_frame(normalized)
    expected = normalized["n_end_selected"] / normalized["n_optical_generated_total"]
    wrong = normalized["n_end_selected"] / normalized["n_scint_generated"]
    assert np.allclose(efficiency["collection_efficiency"], expected)
    assert not np.allclose(efficiency["collection_efficiency"], wrong)
    assert set(efficiency["generated_optical_denominator"]) == {
        "n_optical_generated_total"
    }


def test_component_sum_mismatch_fails_closed():
    mod = _load()
    frame = _current_frame()
    frame.loc[0, "n_optical_generated_total"] += 1
    with pytest.raises(SystemExit, match="does not equal scintillation"):
        mod.normalize_schema(frame)


def test_partial_current_contract_fails_closed():
    mod = _load()
    frame = _current_frame().drop(columns=["n_cerenkov_generated"])
    with pytest.raises(SystemExit, match="Partial current optical contract"):
        mod.normalize_schema(frame)


@pytest.mark.parametrize(
    "column,value,match",
    [
        ("n_wls_generated", np.nan, "nonfinite or nonnumeric"),
        ("n_cerenkov_generated", 1.5, "non-integer counts"),
        ("n_optical_generated_total", -1, "negative values"),
    ],
)
def test_invalid_current_counts_fail_closed(column: str, value: float, match: str):
    mod = _load()
    frame = _current_frame()
    frame[column] = frame[column].astype(float)
    frame.loc[0, column] = value
    with pytest.raises(SystemExit, match=match):
        mod.normalize_schema(frame)


def test_legacy_contract_remains_explicit_and_conservative():
    mod = _load()
    normalized = mod.normalize_schema(_legacy_frame())
    report = mod.validate_physics(normalized)
    assert report["passed"] is True
    assert report["optical_generation_contract"] == "LEGACY_SCINTILLATION_ONLY"
    assert report["generated_optical_denominator"] == "n_scint_generated"
    assert "Legacy input lacks WLS/Cerenkov" in report["optical_bookkeeping"]["limitation"]


def test_main_records_component_and_total_provenance(tmp_path: Path, monkeypatch):
    mod = _load()
    input_path = tmp_path / "normalized.csv"
    output_path = tmp_path / "out"
    _current_frame().to_csv(input_path, index=False)
    monkeypatch.setattr(mod, "make_plots", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--energy-target",
            "both",
        ],
    )
    assert mod.main() == 0
    result = json.loads((output_path / "result.json").read_text(encoding="utf-8"))
    assert result["schema"] == "ccb-single-stave-analysis/2"
    assert result["policy"] == mod.POLICY
    assert result["optical_bookkeeping"]["arrival_bound_denominator"] == (
        "n_optical_generated_total"
    )
    summary = pd.read_csv(output_path / "single_stave_summary.csv")
    assert summary.loc[0, "generated_optical_denominator"] == (
        "n_optical_generated_total"
    )
    assert summary.loc[0, "n_wls_generated_mean"] > 0
    manifest = json.loads((output_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["inputs"][0]["bytes"] == input_path.stat().st_size
    assert len(manifest["inputs"][0]["sha256"]) == 64
