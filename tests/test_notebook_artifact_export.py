"""Artifact-only notebook export tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.notebook_summary import generate_notebook_exports
from ccb_mc_validation.reporting.run_summary import generate_run_summary


def _seed_validated_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-notebook",
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


def test_generate_notebook_exports_writes_jupytext_source_html_manifest(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_validated_run(run)

    manifest = generate_notebook_exports(run)

    assert manifest["status"] == "PASS"
    assert manifest["scope"] == "artifact-summary"
    assert manifest["full_notebook_suite_status"] == "BLOCKED"
    source = run / "notebooks" / "source" / "00_release_overview.py"
    html = run / "notebooks" / "html" / "00_release_overview.html"
    manifest_path = run / "notebooks" / "NOTEBOOKS_MANIFEST.json"
    assert source.is_file()
    assert html.is_file()
    assert manifest_path.is_file()
    source_text = source.read_text(encoding="utf-8")
    assert "formats: py:percent,ipynb" in source_text
    assert "RUN_ID" in source_text
    assert "run-notebook" in source_text
    assert "must not rerun ROOT scans" in source_text
    html_text = html.read_text(encoding="utf-8")
    assert "Partial notebook export" in html_text
    assert "MV4-MV8" in html_text
    assert "run-notebook" in html_text


def test_generate_notebook_exports_rejects_fixture_metrics(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_validated_run(run)
    metrics = run / "reports" / "mc_validation" / "summary" / "metrics_table.csv"
    metrics.write_text(metrics.read_text(encoding="utf-8").replace("PRODUCTION", "FIXTURE", 1), encoding="utf-8")

    try:
        generate_notebook_exports(run)
    except ValueError as exc:
        assert "fixture metrics" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("fixture metrics were accepted")
