from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

uproot = pytest.importorskip("uproot")

SCRIPT = Path(__file__).parents[1] / "scripts" / "compare_single_stave_mt_reproducibility.py"
SPEC = importlib.util.spec_from_file_location("compare_single_stave_mt", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def metadata(n_events: int = 3) -> dict[str, object]:
    return {
        "schema": "ccb-stave-run-meta/1",
        "git_commit": "abc123",
        "geometry_hash": "geometry",
        "seed": 42,
        "particle": "proton",
        "kinetic_energy_MeV": 100.0,
        "n_events": n_events,
        "mode": "optical",
        "birks_kB_mm_per_MeV": 0.126,
        "reflectivity_scale": 1.0,
        "attenuation_scale": 1.0,
        "scintillator_absorption_scale": 1.0,
        "y11_bulk_attenuation_scale": 1.0,
        "pde_scale": 1.0,
        "collection_efficiency": 1.0,
        "optical_interface_model": "UNKNOWN_EXTERNAL",
        "sipm_n_cells": 1600,
        "optical_tables": {"pde": {"path": "pde.csv", "sha256": "deadbeef"}},
        "threads_requested": 1,
        "threads_effective": 1,
        "G4FORCENUMBEROFTHREADS": "",
    }


def write_run(path: Path, event_order: list[int], values: list[float]) -> None:
    numeric = np.asarray(values, dtype=np.float64)
    with uproot.recreate(path) as root_file:
        root_file["events"] = {
            "event": np.asarray(event_order, dtype=np.int32),
            "particle": np.asarray(["proton"] * len(event_order)),
            "edep_scint_MeV": numeric,
            # Keep every synthetic branch attached to the same event row.  The
            # reordered-identical test must reorder all per-event quantities,
            # otherwise it tests a real branch mismatch rather than row-order
            # invariance.
            "n_scint_generated": (numeric * 10).astype(np.int32),
        }


def test_compare_branch_accepts_equal_string_arrays() -> None:
    result = MODULE.compare_branch(
        "particle",
        np.asarray(["proton", "proton"]),
        np.asarray(["proton", "proton"]),
        rtol=0.0,
        atol=0.0,
    )
    assert result.exact_equal
    assert result.allclose
    assert result.n_mismatched == 0


def test_event_id_validation_detects_duplicates_and_missing_ids() -> None:
    result = MODULE.validate_event_ids(np.asarray([0, 1, 1], dtype=np.int32), 3)
    assert not result["valid"]
    assert result["duplicate_ids"] == [1]
    assert result["missing_ids"] == [2]


def test_main_passes_for_reordered_identical_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.root"
    candidate = tmp_path / "candidate.root"
    write_run(reference, [0, 1, 2], [1.0, 2.0, 3.0])
    write_run(candidate, [2, 0, 1], [3.0, 1.0, 2.0])

    reference_meta = tmp_path / "reference.root.meta.json"
    candidate_meta = tmp_path / "candidate.root.meta.json"
    reference_meta.write_text(json.dumps(metadata()), encoding="utf-8")
    candidate_payload = metadata()
    candidate_payload["threads_requested"] = 4
    candidate_payload["threads_effective"] = 4
    candidate_meta.write_text(json.dumps(candidate_payload), encoding="utf-8")

    output_json = tmp_path / "comparison.json"
    output_pdf = tmp_path / "comparison.pdf"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--reference",
            str(reference),
            "--candidate",
            str(candidate),
            "--reference-meta",
            str(reference_meta),
            "--candidate-meta",
            str(candidate_meta),
            "--output-json",
            str(output_json),
            "--output-pdf",
            str(output_pdf),
            "--plot-branches",
            "edep_scint_MeV",
        ],
    )

    assert MODULE.main() == 0
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["pass"]
    assert summary["metadata"]["thread_provenance"]["threads_effective"] == {
        "reference": 1,
        "candidate": 4,
    }
    assert output_pdf.stat().st_size > 0


def test_main_fails_for_event_keyed_numeric_difference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = tmp_path / "reference.root"
    candidate = tmp_path / "candidate.root"
    write_run(reference, [0, 1, 2], [1.0, 2.0, 3.0])
    write_run(candidate, [0, 1, 2], [1.0, 2.5, 3.0])

    reference_meta = tmp_path / "reference.root.meta.json"
    candidate_meta = tmp_path / "candidate.root.meta.json"
    reference_meta.write_text(json.dumps(metadata()), encoding="utf-8")
    candidate_meta.write_text(json.dumps(metadata()), encoding="utf-8")
    output_json = tmp_path / "comparison.json"
    output_pdf = tmp_path / "comparison.pdf"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--reference",
            str(reference),
            "--candidate",
            str(candidate),
            "--reference-meta",
            str(reference_meta),
            "--candidate-meta",
            str(candidate_meta),
            "--output-json",
            str(output_json),
            "--output-pdf",
            str(output_pdf),
            "--plot-branches",
            "edep_scint_MeV",
        ],
    )

    assert MODULE.main() == 1
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    branch = next(row for row in summary["branches"] if row["branch"] == "edep_scint_MeV")
    assert branch["n_mismatched"] == 1
    assert branch["max_abs_diff"] == pytest.approx(0.5)
