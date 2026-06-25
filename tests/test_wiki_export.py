"""GitHub wiki draft export tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.artifact_reports import generate_artifact_reports
from ccb_mc_validation.reporting.claim_ledger import generate_claim_ledger
from ccb_mc_validation.reporting.figure_manifest import generate_summary_figure_manifest
from ccb_mc_validation.reporting.notebook_summary import generate_notebook_exports
from ccb_mc_validation.reporting.notation_registry import generate_notation_registry
from ccb_mc_validation.reporting.open_questions import generate_open_question_registry
from ccb_mc_validation.reporting.question_closure import generate_question_closure_plan
from ccb_mc_validation.reporting.publication_index import generate_publication_index
from ccb_mc_validation.reporting.release_audit import generate_release_audit
from ccb_mc_validation.reporting.run_summary import generate_run_summary
from ccb_mc_validation.reporting.thesis_draft import generate_thesis_draft
from ccb_mc_validation.reporting.visual_review import generate_summary_visual_review
from ccb_mc_validation.reporting.wiki_export import generate_wiki_export


def _seed_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-wiki",
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
    generate_summary_figure_manifest(run)
    generate_summary_visual_review(run)
    generate_notebook_exports(run)
    generate_artifact_reports(run)
    generate_release_audit(run)
    generate_claim_ledger(run)
    generate_release_audit(run, include_claim_ledger=True)
    generate_thesis_draft(run)
    generate_publication_index(run)


def test_generate_wiki_export_writes_github_wiki_pages(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_run(run)

    manifest = generate_wiki_export(run)

    assert manifest["status"] == "PASS"
    assert manifest["scope"] == "github-wiki-draft"
    assert manifest["final_wiki_status"] == "BLOCKED"
    assert manifest["page_count"] >= 5
    wiki = run / "wiki"
    assert (wiki / "Home.md").is_file()
    assert (wiki / "Results-and-Figures.md").is_file()
    assert (wiki / "WIKI_MANIFEST.json").is_file()
    home = (wiki / "Home.md").read_text(encoding="utf-8")
    methods = (wiki / "Methods-and-Mathematics.md").read_text(encoding="utf-8")
    assert "Draft / not final release" in home
    assert "```math" in methods
    assert (wiki / "Notation-and-Equations.md").is_file()
    assert (wiki / "Open-Questions.md").is_file()
    assert "flowchart TD" in (wiki / "Open-Questions.md").read_text(encoding="utf-8")
    assert "AUC" in (wiki / "Results-and-Figures.md").read_text(encoding="utf-8")
    refs = (wiki / "References-and-Reproducibility.md").read_text(encoding="utf-8")
    assert "REF-RUNBOOK" in refs
    assert "final bibliography status" in refs
