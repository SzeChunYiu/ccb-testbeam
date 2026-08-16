"""Tests for LUNARC on-cluster smoke/submit/watch/collect hardening."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def test_cluster_probe_on_lunarc(monkeypatch):
    from ccb_mc_validation.execution.pipeline import PipelineOrchestrator
    orch = PipelineOrchestrator(
        REPO / "configs/mc_validation/smoke.yaml",
        repo_root=REPO,
        profile="smoke",
        run_id="lane10-test",
    )
    monkeypatch.setattr(orch, "_running_on_lunarc", lambda: True)
    assert orch._cluster_probe() == "REACHABLE"
    cmd = orch._slurm_cmd("sacct -X -j 1")
    assert cmd[0] == "bash"


def test_smoke_and_collect_roundtrip():
    from ccb_mc_validation.execution.pipeline import PipelineOrchestrator
    orch = PipelineOrchestrator(
        REPO / "configs/mc_validation/smoke.yaml",
        repo_root=REPO,
        profile="smoke",
        run_id="lane10-smoke",
    )
    run_id = orch.smoke(studies="MV0,MV9")
    assert run_id
    collected = orch.collect()
    assert "artifacts" in collected
    assert collected.get("not_for_physics") is True
