"""Thesis draft generation tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.artifact_reports import generate_artifact_reports
from ccb_mc_validation.reporting.notebook_summary import generate_notebook_exports
from ccb_mc_validation.reporting.release_audit import generate_release_audit
from ccb_mc_validation.reporting.run_summary import generate_run_summary
from ccb_mc_validation.reporting.thesis_draft import generate_thesis_draft


def _seed_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-thesis",
        "status": "PASS",
        "study_metrics": {
            "MV1": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"hgb_auc": 0.9}},
            "MV2": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"proton_ekin_recon_res68": 0.1}},
            "MV3": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10, "n_sample_I": 1, "n_sample_II": 2}, "metrics": {}},
        },
    }
    (run / "VALIDATION.json").write_text(json.dumps(validation), encoding="utf-8")
    generate_run_summary(run)
    generate_notebook_exports(run)
    generate_artifact_reports(run)
    generate_release_audit(run)


def test_generate_thesis_draft_writes_blocked_draft(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_run(run)

    manifest = generate_thesis_draft(run)

    assert manifest["status"] == "PASS"
    assert manifest["scope"] == "artifact-thesis-draft"
    assert manifest["final_thesis_status"] == "BLOCKED"
    assert manifest["blocked_count"] > 0
    out_dir = run / "reports" / "mc_validation" / "thesis_draft"
    md = out_dir / "THESIS_DRAFT.md"
    html = out_dir / "THESIS_DRAFT.html"
    assert md.is_file()
    assert html.is_file()
    text = md.read_text(encoding="utf-8")
    assert "run-thesis" in text
    assert "MV1_REPORT.md" in text
    assert "must not be cited as the final thesis" in text
