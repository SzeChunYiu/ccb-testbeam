"""Fail-closed production orchestration regression tests."""

from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.execution.pipeline import DAG, PipelineOrchestrator

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/mc_validation/execution.yaml"


def test_dag_includes_mv4_through_mv8_and_publication_tasks() -> None:
    for task in ["prod_MV4", "prod_MV5", "prod_MV6", "prod_MV7", "prod_MV8", "prod_systematics", "figures", "notebooks", "docs", "thesis", "release"]:
        assert task in DAG
    assert DAG["prod_MV4"] == ["prod_MV0"]


def test_production_preflight_blocks_missing_inputs_and_lunarc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(PipelineOrchestrator, "_cluster_probe", lambda self: "UNREACHABLE (test)")
    monkeypatch.setenv("CCB_ARTIFACT_ROOT", str(tmp_path))
    orch = PipelineOrchestrator(CONFIG, repo_root=ROOT, profile="production")
    result = orch.preflight(allow_dirty=True)
    assert result["status"] == "BLOCKED"
    statuses = {c["name"]: c["status"] for c in result["checks"]}
    assert statuses["lunarc_socket"] == "BLOCKED"
    assert statuses["mc_root"] in {"MISSING", "PASS"}


def test_submit_records_blocker_instead_of_local_production(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(PipelineOrchestrator, "_cluster_probe", lambda self: "UNREACHABLE (test)")
    monkeypatch.setenv("CCB_ARTIFACT_ROOT", str(tmp_path))
    orch = PipelineOrchestrator(CONFIG, repo_root=ROOT, profile="production")
    result = orch.submit(studies="all")
    assert result["status"] == "BLOCKED"
    assert "resume_command" in result
    blocker = orch.run_path / "blockers" / "PRODUCTION_SUBMIT_BLOCKED.json"
    assert blocker.is_file()
