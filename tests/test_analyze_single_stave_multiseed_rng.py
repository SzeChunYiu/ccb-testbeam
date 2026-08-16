from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

uproot = pytest.importorskip("uproot")

SCRIPT = Path(__file__).parents[1] / "scripts" / "analyze_single_stave_multiseed_rng.py"
SPEC = importlib.util.spec_from_file_location("analyze_single_stave_multiseed_rng", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def metadata(seed: int, threads: int, n_events: int = 4) -> dict[str, object]:
    return {
        "schema": "ccb-stave-run-meta/1",
        "git_commit": "abc123",
        "geometry_hash": "geometry",
        "seed": seed,
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
        "threads_requested": threads,
        "threads_effective": threads,
        "G4FORCENUMBEROFTHREADS": "",
    }


def write_run(path: Path, offset: float) -> None:
    patterns = {
        0: np.asarray([1.0, 2.0, 4.0, 8.0]),
        1: np.asarray([2.0, 8.0, 1.0, 4.0]),
        2: np.asarray([8.0, 1.0, 4.0, 2.0]),
        3: np.asarray([4.0, 2.0, 8.0, 1.0]),
    }
    key = int(round(offset * 10))
    values = patterns[key]
    with uproot.recreate(path) as root_file:
        root_file["events"] = {
            "event": np.arange(4, dtype=np.int32),
            "edep_scint_MeV": values,
            "n_scint_generated": (values * 10).astype(np.int32),
        }


def build_manifest(tmp_path: Path, specs: list[tuple[int, int, float]]) -> Path:
    rows = []
    for index, (seed, threads, offset) in enumerate(specs):
        root = tmp_path / f"run_{index}.root"
        meta = tmp_path / f"run_{index}.root.meta.json"
        write_run(root, offset)
        meta.write_text(json.dumps(metadata(seed, threads)), encoding="utf-8")
        rows.append(
            {
                "root": str(root),
                "meta": str(meta),
                "label": f"run{index}-s{seed}-t{threads}",
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"runs": rows}), encoding="utf-8")
    return manifest


def test_main_passes_for_two_seed_thread_groups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = build_manifest(
        tmp_path,
        [
            (101, 1, 0.0),
            (102, 1, 0.1),
            (101, 4, 0.0),
            (102, 4, 0.1),
        ],
    )
    output_json = tmp_path / "summary.json"
    output_pdf = tmp_path / "summary.pdf"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--output-json",
            str(output_json),
            "--output-pdf",
            str(output_pdf),
            "--observables",
            "edep_scint_MeV",
            "n_scint_generated",
            "--minimum-seeds-per-thread",
            "2",
        ],
    )

    assert MODULE.main() == 0
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["pass"]
    assert not summary["duplicate_seeds_within_effective_thread_group"]
    assert not summary["duplicate_streams_across_different_seeds"]
    assert all(row["pass"] for row in summary["thread_group_effects"])
    assert all(row["pass"] for row in summary["cross_seed_event_index_correlations"])
    assert output_pdf.stat().st_size > 0


def test_detects_exact_duplicate_streams_across_different_seeds(tmp_path: Path) -> None:
    manifest = build_manifest(
        tmp_path,
        [
            (101, 1, 0.0),
            (102, 1, 0.0),
            (103, 1, 0.2),
            (104, 1, 0.3),
        ],
    )
    rows = MODULE.load_manifest(manifest)
    summary = MODULE.build_summary(
        rows,
        "events",
        ["edep_scint_MeV", "n_scint_generated"],
        minimum_seeds_per_thread=4,
        max_thread_effect_z=3.0,
        max_seed_outlier_z=10.0,
        max_cross_seed_correlation_z=10.0,
        allow_different_git_commit=False,
    )
    assert not summary["pass"]
    assert len(summary["duplicate_streams_across_different_seeds"]) == 1
    duplicate = summary["duplicate_streams_across_different_seeds"][0]
    assert {duplicate["left_seed"], duplicate["right_seed"]} == {101, 102}


def test_rejects_duplicate_seed_within_thread_group(tmp_path: Path) -> None:
    manifest = build_manifest(
        tmp_path,
        [
            (101, 1, 0.0),
            (101, 1, 0.1),
            (102, 1, 0.2),
            (103, 1, 0.3),
        ],
    )
    rows = MODULE.load_manifest(manifest)
    summary = MODULE.build_summary(
        rows,
        "events",
        ["edep_scint_MeV"],
        minimum_seeds_per_thread=3,
        max_thread_effect_z=3.0,
        max_seed_outlier_z=10.0,
        max_cross_seed_correlation_z=10.0,
        allow_different_git_commit=False,
    )
    assert not summary["pass"]
    assert summary["duplicate_seeds_within_effective_thread_group"][0]["seed"] == 101


def test_rejects_insufficient_seed_coverage(tmp_path: Path) -> None:
    manifest = build_manifest(tmp_path, [(101, 1, 0.0), (102, 1, 0.1)])
    rows = MODULE.load_manifest(manifest)
    summary = MODULE.build_summary(
        rows,
        "events",
        ["edep_scint_MeV"],
        minimum_seeds_per_thread=4,
        max_thread_effect_z=3.0,
        max_seed_outlier_z=10.0,
        max_cross_seed_correlation_z=10.0,
        allow_different_git_commit=False,
    )
    assert not summary["pass"]
    assert not summary["seed_coverage_by_effective_thread_count"]["1"]["pass"]
