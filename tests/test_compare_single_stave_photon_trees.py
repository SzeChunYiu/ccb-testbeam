from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

uproot = pytest.importorskip("uproot")

SCRIPT = Path(__file__).parents[1] / "scripts" / "compare_single_stave_photon_trees.py"
SPEC = importlib.util.spec_from_file_location("compare_single_stave_photons", SCRIPT)
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
    }


def photons(order: list[int] | None = None) -> dict[str, np.ndarray]:
    payload = {
        "event": np.asarray([0, 0, 1, 2, 2], dtype=np.int32),
        "sensor": np.asarray([0, 1, 2, 3, 0], dtype=np.int32),
        "wavelength_nm": np.asarray([420.0, 421.0, 430.0, 440.0, 450.0]),
        "time_ns": np.asarray([1.0, 1.2, 2.0, 3.0, 3.5]),
        "path_len_mm": np.asarray([100.0, 110.0, 200.0, 300.0, 350.0]),
        "detected": np.asarray([1, 0, 1, 0, 1], dtype=np.int32),
    }
    if order is None:
        return payload
    indices = np.asarray(order, dtype=int)
    return {name: values[indices] for name, values in payload.items()}


def write_run(path: Path, payload: dict[str, np.ndarray]) -> None:
    with uproot.recreate(path) as root_file:
        root_file["photons"] = payload


def invoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reference_payload: dict[str, np.ndarray],
    candidate_payload: dict[str, np.ndarray],
) -> tuple[int, dict[str, object], Path]:
    reference = tmp_path / "reference.root"
    candidate = tmp_path / "candidate.root"
    write_run(reference, reference_payload)
    write_run(candidate, candidate_payload)

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
        ],
    )
    result = MODULE.main()
    return result, json.loads(output_json.read_text(encoding="utf-8")), output_pdf


def test_integrity_rejects_invalid_foreign_keys_and_domains() -> None:
    payload = photons()
    payload["event"][0] = 3
    payload["sensor"][1] = 9
    payload["detected"][2] = 2
    payload["wavelength_nm"][3] = -1.0
    payload["time_ns"][4] = -0.1
    payload["path_len_mm"][0] = np.nan

    result = MODULE.validate_photons(payload, n_events=3)

    assert not result["valid"]
    assert result["checks"]["event_foreign_keys"]["invalid_rows"] == 1
    assert result["checks"]["sensor_domain"]["invalid_rows"] == 1
    assert result["checks"]["detected_domain"]["invalid_rows"] == 1
    assert result["checks"]["wavelength_domain"]["nonpositive_rows"] == 1
    assert result["checks"]["time_domain"]["negative_rows"] == 1
    assert result["checks"]["path_domain"]["nonfinite_rows"] == 1


def test_main_passes_for_same_photon_multiset_in_different_row_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, summary, output_pdf = invoke(
        tmp_path,
        monkeypatch,
        photons(),
        photons([4, 2, 0, 3, 1]),
    )

    assert result == 0
    assert summary["pass"]
    assert summary["integrity"]["reference"]["valid"]
    assert summary["integrity"]["candidate"]["valid"]
    assert all(item["exact_equal"] for item in summary["fields"])
    assert summary["aggregates"]["reference"]["rows"] == 5
    assert output_pdf.stat().st_size > 0


def test_main_fails_for_changed_photon_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = photons()
    candidate["time_ns"][2] = 2.25

    result, summary, _ = invoke(tmp_path, monkeypatch, photons(), candidate)

    assert result == 1
    field = next(item for item in summary["fields"] if item["field"] == "time_ns")
    assert field["n_mismatched"] == 1
    assert field["max_abs_diff"] == pytest.approx(0.25)


def test_main_fails_for_missing_photon_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = {name: values[:-1] for name, values in photons().items()}

    result, summary, _ = invoke(tmp_path, monkeypatch, photons(), candidate)

    assert result == 1
    assert not summary["row_counts_match"]
    assert not summary["pass"]
