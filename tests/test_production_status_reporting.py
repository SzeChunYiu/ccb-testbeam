"""Production blocker reporting regressions."""

from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.execution.pipeline import PipelineOrchestrator

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/mc_validation/execution.yaml"


def test_blocked_submit_writes_human_status_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(PipelineOrchestrator, "_cluster_probe", lambda self: "UNREACHABLE (test)")
    monkeypatch.setenv("CCB_ARTIFACT_ROOT", str(tmp_path))
    orch = PipelineOrchestrator(CONFIG, repo_root=ROOT, profile="production")

    result = orch.submit(studies="all")

    assert result["status"] == "BLOCKED"
    report = orch.run_path / "reports" / "PRODUCTION_STATUS.md"
    payload = orch.run_path / "reports" / "PRODUCTION_STATUS.json"
    assert report.is_file()
    assert payload.is_file()
    text = report.read_text(encoding="utf-8")
    assert "Production claims allowed:** `False`" in text
    assert "No production SLURM jobs submitted" in text
    assert "Fixture/smoke outputs" in text or "No smoke gate" in text
