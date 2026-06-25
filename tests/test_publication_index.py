"""Publication index draft tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.artifact_reports import generate_artifact_reports
from ccb_mc_validation.reporting.notebook_summary import generate_notebook_exports
from ccb_mc_validation.reporting.notation_registry import generate_notation_registry
from ccb_mc_validation.reporting.open_questions import generate_open_question_registry
from ccb_mc_validation.reporting.question_closure import generate_question_closure_plan
from ccb_mc_validation.reporting.publication_index import generate_publication_index
from ccb_mc_validation.reporting.release_audit import generate_release_audit
from ccb_mc_validation.reporting.run_summary import generate_run_summary
from ccb_mc_validation.reporting.thesis_draft import generate_thesis_draft


def _seed_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-publication",
        "status": "PASS",
        "study_metrics": {
            "MV1": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"hgb_auc": 0.9}},
            "MV2": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"proton_ekin_recon_res68": 0.1}},
            "MV3": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10, "n_sample_I": 1, "n_sample_II": 2}, "metrics": {}},
        },
    }
    (run / "VALIDATION.json").write_text(json.dumps(validation), encoding="utf-8")
    (run / "VALIDATION_SUMMARY.md").write_text("# validation\n", encoding="utf-8")
    generate_run_summary(run)
    from ccb_mc_validation.reporting.figure_manifest import generate_summary_figure_manifest
    generate_summary_figure_manifest(run)
    from ccb_mc_validation.reporting.visual_review import generate_summary_visual_review
    generate_summary_visual_review(run)
    generate_notebook_exports(run)
    generate_artifact_reports(run)
    generate_release_audit(run)
    from ccb_mc_validation.reporting.claim_ledger import generate_claim_ledger
    generate_claim_ledger(run)
    from ccb_mc_validation.reporting.reference_registry import generate_reference_registry
    generate_reference_registry(run)
    generate_notation_registry(run)
    generate_open_question_registry(run)
    generate_question_closure_plan(run)
    generate_thesis_draft(run)


def test_publication_index_writes_draft_index_and_manifest(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_run(run)

    manifest = generate_publication_index(run)

    assert manifest["status"] == "BLOCKED"
    assert manifest["scope"] == "publication-index-draft"
    assert manifest["release_ready"] is False
    assert manifest["missing"] == []
    assert manifest["blocked_count"] > 0
    index = run / "publication" / "index.html"
    md = run / "publication" / "INDEX.md"
    assert index.is_file()
    assert md.is_file()
    html = index.read_text(encoding="utf-8")
    assert "Draft / blocked" in html
    assert "THESIS_DRAFT.html" in html
    assert "FIGURE_CONTACT_SHEET.html" in html
    assert "visual_review.html" in html
    assert "CLAIM_LEDGER.md" in html
    assert "REFERENCE_REGISTRY.md" in html
    assert "NOTATION_REGISTRY.md" in html
    assert "OPEN_QUESTIONS.md" in html
    assert "OPEN_QUESTION_CLOSURE_PLAN.md" in html
    text = md.read_text(encoding="utf-8")
    assert "run-publication" in text
    assert "Remaining release blockers" in text
