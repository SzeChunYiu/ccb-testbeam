"""Smoke/collect path must be DAG-ready for later orchestrated runs."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_smoke_and_collect_roundtrip(tmp_path, monkeypatch):
    from ccb_mc_validation.execution.pipeline import PipelineOrchestrator

    # Keep artifacts under tmp if orchestrator honors repo_root paths
    orch = PipelineOrchestrator(
        REPO / "configs/mc_validation/smoke.yaml",
        repo_root=REPO,
        profile="smoke",
        run_id="lane10-waveC-smoke",
    )
    monkeypatch.setattr(orch, "_running_on_lunarc", lambda: True)
    assert orch._cluster_probe() == "REACHABLE"
    run_id = orch.smoke(studies="MV0,MV9")
    assert run_id
    collected = orch.collect()
    assert "artifacts" in collected
    assert collected.get("not_for_physics") is True
    assert collected.get("dag_ready") is True
