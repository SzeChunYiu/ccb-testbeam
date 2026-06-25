"""Artifact validation summary tests."""

from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.execution.pipeline import PipelineOrchestrator

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/mc_validation/execution.yaml"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validate_accepts_complete_artifacted_run(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CCB_ARTIFACT_ROOT", str(tmp_path))
    orch = PipelineOrchestrator(CONFIG, repo_root=ROOT, profile="production", run_id="run1")
    run = orch._ensure_run("run1")
    _write_json(run / "JOB_STATE.json", {"job_id": "123", "state": "COMPLETED", "exit_code": "0:0"})
    _write_json(
        run / "execution" / "PREFLIGHT.json",
        {
            "checks": [
                {"name": "mc_root", "status": "PASS", "path": "/x.root", "sha256": "abc"},
                {"name": "data_pulses", "status": "PASS", "path": "/x.csv.gz", "sha256": "def"},
            ]
        },
    )
    for rel in ["mv1_pid", "mv2_energy", "mv3_stopping_depth"]:
        _write_json(
            run / "reports" / "mc_validation" / rel / "study_result.json",
            {"study_id": rel, "status": "PRODUCTION", "metrics": {"hgb_auc": 0.9}, "cutflow": {"n_tracks": 10}},
        )
    mv9 = run / "reports" / "mc_validation" / "mv9_synthesis" / "MV9_SYNTHESIS.md"
    mv9.parent.mkdir(parents=True, exist_ok=True)
    mv9.write_text("| MV1 | PRODUCTION | x |\n| MV4 | BLOCKED | y |\n", encoding="utf-8")
    logs = run / "logs"
    logs.mkdir()
    (logs / "ccb_mc_validation_123.out").write_text("ok", encoding="utf-8")

    report = orch.validate(run_id="run1", scope="artifact", strict=True)

    assert report["status"] == "PASS"
    assert (run / "VALIDATION_SUMMARY.md").is_file()
    assert "MV1" in (run / "VALIDATION_SUMMARY.md").read_text(encoding="utf-8")
