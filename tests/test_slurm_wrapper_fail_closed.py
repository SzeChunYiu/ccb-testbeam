"""SLURM wrapper safety checks."""

from __future__ import annotations

import subprocess
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


def test_mc_validation_wrapper_is_bash_syntax_valid() -> None:
    subprocess.run(["bash", "-n", str(WRAPPER)], check=True)


def test_mc_validation_wrapper_generates_release_artifacts_in_allocation() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    ordered_needles = [
        'run_step "validate artifacts"',
        'run_step "summary figures"',
        'run_step "notebook HTML"',
        'run_step "artifact reports"',
        'run_step "QA audit"',
        'run_step "thesis draft"',
        'run_step "release and wiki draft"',
    ]
    positions = [text.index(needle) for needle in ordered_needles]
    assert positions == sorted(positions)
    assert 'cat > "${RUN_ROOT}/JOB_STATE.json"' in text
    assert positions[0] > text.index('cat > "${RUN_ROOT}/JOB_STATE.json"')
