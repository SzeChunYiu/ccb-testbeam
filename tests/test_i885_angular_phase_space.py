"""I885 normal-incidence angular undercoverage gate (#1093)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "geant4/single_stave/slurm/make_i885_campaign.py"
VALIDATE = REPO / "tools/audit/validate_i885_angular_phase_space.py"


def test_campaign_declares_normal_incidence_only():
    text = (REPO / "geant4/single_stave/slurm/points_i885_campaign.csv").read_text(encoding="utf-8")
    assert "NORMAL_INCIDENCE_ONLY" in text
    assert "theta_deg=0.0" in text
    assert "phi_deg=0.0" in text
    assert "BLOCKED" in text


def test_nonzero_angles_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    out = tmp_path / "points.csv"
    env = {**os.environ, "CCB_I885_THETA_DEG": "10", "CCB_I885_PHI_DEG": "0"}
    proc = subprocess.run(
        [sys.executable, str(GEN), "--out", str(out)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
    )
    assert proc.returncode != 0
    assert "NORMAL_INCIDENCE_ONLY" in (proc.stderr + proc.stdout)


def test_validator_passes():
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), "--repo-root", str(REPO)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
