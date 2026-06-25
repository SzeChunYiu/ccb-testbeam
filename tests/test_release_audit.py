"""Release QA audit tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.artifact_reports import generate_artifact_reports
from ccb_mc_validation.reporting.notebook_summary import generate_notebook_exports
from ccb_mc_validation.reporting.release_audit import generate_release_audit
from ccb_mc_validation.reporting.run_summary import generate_run_summary


def _seed_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-audit",
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


def test_release_audit_writes_fail_closed_gap_matrix(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_run(run)

    audit = generate_release_audit(run)

    assert audit["status"] == "BLOCKED"
    assert audit["release_ready"] is False
    checks = {check["name"]: check for check in audit["checks"]}
    assert checks["artifact_validation"]["status"] == "PASS"
    assert checks["MV1_production_artifact"]["status"] == "PASS"
    assert checks["MV4_production_artifact"]["status"] == "BLOCKED"
    assert checks["thesis_pdf_html"]["status"] == "BLOCKED"
    assert (run / "QA_RELEASE_AUDIT.json").is_file()
    md = (run / "QA_RELEASE_AUDIT.md").read_text(encoding="utf-8")
    assert "release QA audit" in md
    assert "MV4_production_artifact" in md
    assert "Release ready:** `False`" in md
