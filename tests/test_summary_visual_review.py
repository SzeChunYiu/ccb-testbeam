"""Summary visual-review artifact tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.figure_manifest import generate_summary_figure_manifest
from ccb_mc_validation.reporting.run_summary import generate_run_summary
from ccb_mc_validation.reporting.visual_review import generate_summary_visual_review


def _seed_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-visual",
        "status": "PASS",
        "study_metrics": {
            "MV1": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"hgb_auc": 0.9}},
            "MV2": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"proton_ekin_recon_res68": 0.1}},
            "MV3": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10, "n_sample_I": 1, "n_sample_II": 2}, "metrics": {}},
        },
    }
    (run / "VALIDATION.json").write_text(json.dumps(validation), encoding="utf-8")
    generate_run_summary(run)
    generate_summary_figure_manifest(run)


def test_generate_summary_visual_review_records_scoped_review(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_run(run)

    review = generate_summary_visual_review(run)

    assert review["status"] == "PASS"
    assert review["scope"] == "summary-figure-visual-review"
    assert review["full_visual_review_status"] == "BLOCKED"
    assert review["review_count"] == 2
    figure_dir = run / "figures" / "summary"
    assert (figure_dir / "visual_review.json").is_file()
    assert (figure_dir / "visual_review.md").is_file()
    assert (figure_dir / "visual_review.html").is_file()
    text = (figure_dir / "visual_review.md").read_text(encoding="utf-8")
    assert "codex-automated-visual-qa" in text
    assert "full thesis/release figure catalog" in text
