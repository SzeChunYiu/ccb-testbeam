"""SLURM wrapper safety checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "geant4" / "jobs" / "mc_validation_pipeline.sbatch"


def test_mc_validation_wrapper_does_not_swallow_failures() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "SLURM_JOB_ID" in text
    assert "skipped (not yet wired)" not in text
    assert "|| echo \"[pipeline]" not in text
    assert "run_step" in text
