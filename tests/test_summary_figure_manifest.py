"""Summary figure manifest tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.figure_manifest import generate_summary_figure_manifest
from ccb_mc_validation.reporting.run_summary import generate_run_summary


def _seed_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-figures",
        "status": "PASS",
        "study_metrics": {
            "MV1": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"hgb_auc": 0.9}},
            "MV2": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"proton_ekin_recon_res68": 0.1}},
            "MV3": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10, "n_sample_I": 1, "n_sample_II": 2}, "metrics": {}},
        },
    }
    (run / "VALIDATION.json").write_text(json.dumps(validation), encoding="utf-8")
    generate_run_summary(run)


def test_generate_summary_figure_manifest_writes_contact_sheets(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_run(run)

    manifest = generate_summary_figure_manifest(run)

    assert manifest["status"] == "PASS"
    assert manifest["scope"] == "summary-figure-manifest"
    assert manifest["full_figure_catalog_status"] == "BLOCKED"
    assert {fig["id"] for fig in manifest["figures"]} == {"SUMMARY-F001", "SUMMARY-F002"}
    figure_dir = run / "figures" / "summary"
    assert (figure_dir / "FIGURE_MANIFEST.json").is_file()
    assert (figure_dir / "FIGURE_CONTACT_SHEET.md").is_file()
    assert (figure_dir / "FIGURE_CONTACT_SHEET.html").is_file()
    text = (figure_dir / "FIGURE_CONTACT_SHEET.md").read_text(encoding="utf-8")
    assert "Alt text" in text
    assert "metrics_table.csv" in text
