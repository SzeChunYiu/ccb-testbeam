"""Artifact-backed report generation tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.artifact_reports import generate_artifact_reports
from ccb_mc_validation.reporting.run_summary import generate_run_summary


def _seed_validated_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-report",
        "status": "PASS",
        "job_state": {"job_id": "123", "state": "COMPLETED", "exit_code": "0:0"},
        "study_metrics": {
            "MV1": {"status": "PRODUCTION", "cutflow": {"n_tracks": 100}, "metrics": {"hgb_auc": 0.99}},
            "MV2": {"status": "PRODUCTION", "cutflow": {"n_tracks": 100}, "metrics": {"proton_ekin_recon_res68": 0.1}},
            "MV3": {"status": "PRODUCTION", "cutflow": {"n_tracks": 100, "n_sample_I": 10, "n_sample_II": 20}, "metrics": {}},
        },
    }
    (run / "VALIDATION.json").write_text(json.dumps(validation), encoding="utf-8")
    generate_run_summary(run)


def test_generate_artifact_reports_writes_global_and_study_reports(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_validated_run(run)

    manifest = generate_artifact_reports(run)

    assert manifest["status"] == "PASS"
    assert manifest["scope"] == "artifact-summary"
    assert manifest["full_report_suite_status"] == "BLOCKED"
    assert "MV4" in manifest["blocked_studies"]
    report_dir = run / "reports" / "mc_validation" / "artifact_reports"
    assert (report_dir / "GLOBAL_REPORT.md").is_file()
    assert (report_dir / "GLOBAL_REPORT.html").is_file()
    assert (report_dir / "MV1_REPORT.md").is_file()
    assert (report_dir / "MV1_REPORT.html").is_file()
    assert (report_dir / "REPORTS_MANIFEST.json").is_file()
    text = (report_dir / "GLOBAL_REPORT.md").read_text(encoding="utf-8")
    assert "run-report" in text
    assert "MV4" in text
    assert "not the final figure catalog" in text


def test_generate_artifact_reports_rejects_fixture_metrics(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_validated_run(run)
    metrics = run / "reports" / "mc_validation" / "summary" / "metrics_table.csv"
    metrics.write_text(metrics.read_text(encoding="utf-8").replace("PRODUCTION", "FIXTURE", 1), encoding="utf-8")

    try:
        generate_artifact_reports(run)
    except ValueError as exc:
        assert "fixture metrics" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("fixture metrics were accepted")
