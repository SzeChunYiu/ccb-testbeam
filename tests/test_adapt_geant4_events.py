from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "single_stave"
    / "adapt_geant4_events.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("adapt_geant4_events", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _current_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event": [0, 1],
            "particle": ["proton", "deuteron"],
            "ke_MeV": [100.0, 80.0],
            "edep_scint_MeV": [12.5, 15.0],
            "edep_scint_raw_MeV": [13.0, 16.0],
            "track_len_scint_mm": [20.0, 12.5],
            "n_scint_generated": [10, 20],
            "n_wls_generated": [5, 0],
            "n_cerenkov_generated": [0, 2],
            "arrival_readout": [12, 18],
            "detected_readout": [4, 7],
        }
    )


def test_current_tree_maps_exactly_and_converts_track_units():
    mod = _load()
    out = mod.adapt_current_events(_current_frame(), "run-001")
    assert out["event_id"].tolist() == [0, 1]
    assert out["particle_pdg"].tolist() == [2212, 1000010020]
    assert out["kinetic_energy_MeV"].tolist() == [100.0, 80.0]
    assert out["n_end_selected"].tolist() == [12, 18]
    assert out["n_detected_pe"].tolist() == [4, 7]
    assert out["track_length_scint_cm"].tolist() == [2.0, 1.25]
    assert out["n_optical_generated_total"].tolist() == [15, 22]
    assert set(out["run_id"]) == {"run-001"}


def test_wls_and_cerenkov_are_included_in_arrival_bound():
    mod = _load()
    frame = _current_frame().iloc[[0]].copy()
    assert frame.iloc[0]["arrival_readout"] > frame.iloc[0]["n_scint_generated"]
    out = mod.adapt_current_events(frame, "run-wls")
    assert out.iloc[0]["n_end_selected"] == 12
    assert out.iloc[0]["n_optical_generated_total"] == 15


def test_arrivals_above_total_generated_fail_closed():
    mod = _load()
    frame = _current_frame()
    frame.loc[0, "arrival_readout"] = 16
    with pytest.raises(ValueError, match="exceeds total generated optical tracks"):
        mod.adapt_current_events(frame, "run-bad")


def test_detected_above_arrivals_fails_closed():
    mod = _load()
    frame = _current_frame()
    frame.loc[0, "detected_readout"] = 13
    with pytest.raises(ValueError, match="n_detected_pe exceeds n_end_selected"):
        mod.adapt_current_events(frame, "run-bad")


@pytest.mark.parametrize(
    "column,value,match",
    [
        ("arrival_readout", np.nan, "nonfinite or nonnumeric"),
        ("n_wls_generated", 1.5, "non-integer counts"),
        ("detected_readout", -1, "negative values"),
    ],
)
def test_invalid_counts_fail_closed(column: str, value: float, match: str):
    mod = _load()
    frame = _current_frame()
    frame[column] = frame[column].astype(float)
    frame.loc[0, column] = value
    with pytest.raises(ValueError, match=match):
        mod.adapt_current_events(frame, "run-bad")


def test_source_and_normalized_columns_cannot_coexist():
    mod = _load()
    frame = _current_frame()
    frame["n_end_selected"] = frame["arrival_readout"]
    with pytest.raises(ValueError, match="ambiguous source and normalized"):
        mod.adapt_current_events(frame, "run-ambiguous")


def test_current_run_action_branch_contract_is_covered():
    mod = _load()
    run_action = (
        Path(__file__).resolve().parents[1]
        / "geant4"
        / "single_stave"
        / "src"
        / "RunAction.cc"
    )
    if not run_action.exists():
        pytest.skip("repository RunAction.cc is not present in isolated test fixture")
    source = run_action.read_text(encoding="utf-8")
    for branch in sorted(mod.REQUIRED_CURRENT):
        assert f'"{branch}"' in source
    assert mod.CURRENT_TO_NORMALIZED["arrival_readout"] == "n_end_selected"
    assert mod.CURRENT_TO_NORMALIZED["detected_readout"] == "n_detected_pe"


def test_cli_writes_atomic_output_and_machine_readable_mapping(tmp_path: Path):
    input_path = tmp_path / "events.csv"
    output_path = tmp_path / "normalized.csv"
    metadata_path = tmp_path / "mapping.json"
    _current_frame().to_csv(input_path, index=False)

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--metadata",
            str(metadata_path),
            "--run-id",
            "run-cli",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["status"] == "VALIDATED"
    assert payload["mapping"]["arrival_readout"] == "n_end_selected"
    assert payload["mapping"]["detected_readout"] == "n_detected_pe"
    assert payload["selected_sensor"] == "readout = fibre 1, +x physical readout"
    assert payload["output"]["rows"] == 2
    assert pd.read_csv(output_path)["run_id"].tolist() == ["run-cli", "run-cli"]
    assert not list(tmp_path.glob(".*.tmp"))


def test_cli_refuses_existing_outputs_without_overwrite(tmp_path: Path):
    input_path = tmp_path / "events.csv"
    output_path = tmp_path / "normalized.csv"
    metadata_path = tmp_path / "mapping.json"
    _current_frame().to_csv(input_path, index=False)
    output_path.write_text("preserve me", encoding="utf-8")
    before = output_path.read_bytes()
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--metadata",
            str(metadata_path),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "refusing to overwrite" in proc.stderr
    assert output_path.read_bytes() == before


def test_cli_rejects_input_output_alias(tmp_path: Path):
    input_path = tmp_path / "events.csv"
    _current_frame().to_csv(input_path, index=False)
    before = input_path.read_bytes()
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(input_path),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "must not alias the input" in proc.stderr
    assert input_path.read_bytes() == before
