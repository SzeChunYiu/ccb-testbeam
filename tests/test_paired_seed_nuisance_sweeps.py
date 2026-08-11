"""Paired multi-seed nuisance sweeps (#984)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "geant4/single_stave/slurm/grids/generate_points.py"
VALIDATE = REPO / "tools/audit/validate_paired_seed_design.py"


def _load_gen():
    spec = importlib.util.spec_from_file_location("generate_points", GEN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_emit_reuses_seed_across_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CCB_CAMPASSIGN_SEED_REPLICATES", "42,43")
    monkeypatch.setenv("CCB_GRID_PDE_SCALE", "0.8,1.0,1.2")
    # Reload after env change
    if "generate_points" in sys.modules:
        del sys.modules["generate_points"]
    # Call via subprocess for clean env
    out = tmp_path / "grids"
    out.mkdir()
    proc = subprocess.run(
        [sys.executable, str(GEN), "--outdir", str(out), "--knobs", "pde_scale",
         "--seed-replicates", "42,43"],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env={**os.environ, "CCB_GRID_PDE_SCALE": "0.8,1.0,1.2"},
    )
    assert proc.returncode == 0
    csv_text = (out / "points_pde_scale.csv").read_text(encoding="utf-8")
    data = [ln for ln in csv_text.splitlines() if ln and not ln.startswith("#") and not ln.startswith("label")]
    assert len(data) == 6  # 3 values x 2 seeds
    seeds_for_values = {}
    for ln in data:
        label, seed, *_ = ln.split(",")
        val = label.split("__rep=")[0]
        seeds_for_values.setdefault(val, set()).add(seed)
    # Each value appears under both seeds
    for val, seeds in seeds_for_values.items():
        assert seeds == {"42", "43"}, val
    # Same seed appears at every value (CRN)
    by_seed = {}
    for ln in data:
        label, seed, *_ = ln.split(",")
        by_seed.setdefault(seed, set()).add(label.split("__rep=")[0])
    assert by_seed["42"] == by_seed["43"]
    assert len(by_seed["42"]) == 3
    design = json.loads((out / "PAIRED_SEED_DESIGN.json").read_text(encoding="utf-8"))
    assert design["design"] == "common_random_number"
    assert design["seed_replicates"] == [42, 43]
    assert all("replicate_seed" in r for r in design["rows"])


def test_repo_grids_pass_validator():
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), "--repo-root", str(REPO)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout
