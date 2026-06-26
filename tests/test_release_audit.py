"""Release QA audit tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.artifact_reports import generate_artifact_reports
from ccb_mc_validation.reporting.notebook_summary import generate_notebook_exports
from ccb_mc_validation.reporting.open_questions import generate_open_question_registry
from ccb_mc_validation.reporting.publication_index import generate_publication_index
from ccb_mc_validation.reporting.question_closure import generate_question_closure_plan
from ccb_mc_validation.reporting.evidence_packets import generate_evidence_packets
from ccb_mc_validation.reporting.study_gap_audit import generate_study_gap_audit
from ccb_mc_validation.reporting.thesis_draft import generate_thesis_draft
from ccb_mc_validation.reporting.claim_ledger import generate_claim_ledger
from ccb_mc_validation.reporting.figure_manifest import generate_summary_figure_manifest
from ccb_mc_validation.reporting.visual_review import generate_summary_visual_review
from ccb_mc_validation.reporting.release_audit import generate_release_audit
from ccb_mc_validation.reporting.run_summary import generate_run_summary
from ccb_mc_validation.reporting.wiki_export import generate_wiki_export


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
    generate_summary_figure_manifest(run)
    generate_summary_visual_review(run)
    generate_notebook_exports(run)
    generate_artifact_reports(run)
    generate_open_question_registry(run)
    generate_question_closure_plan(run)
    generate_evidence_packets(run)
    generate_study_gap_audit(run)
    generate_release_audit(run)
    generate_claim_ledger(run)


def test_release_audit_writes_fail_closed_gap_matrix(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_run(run)

    audit = generate_release_audit(run, include_claim_ledger=True)

    assert audit["status"] == "BLOCKED"
    assert audit["release_ready"] is False
    checks = {check["name"]: check for check in audit["checks"]}
    assert checks["artifact_validation"]["status"] == "PASS"
    assert checks["MV1_production_artifact"]["status"] == "PASS"
    assert checks["summary_figure_manifest"]["status"] == "PASS"
    assert checks["summary_visual_review"]["status"] == "PASS"
    assert checks["claim_ledger"]["status"] == "PASS"
    assert checks["wiki_claim_evidence_matrix"]["status"] == "BLOCKED"
    assert checks["wiki_claim_evidence_matrix"]["reason"] == "missing wiki manifest"
    assert checks["open_question_registry"]["status"] == "PASS"
    assert checks["open_question_closure_plan"]["status"] == "PASS"
    assert checks["all_questions_closed"]["status"] == "BLOCKED"
    assert checks["all_question_steps_closed"]["status"] == "BLOCKED"
    assert checks["open_question_evidence_packets"]["status"] == "PASS"
    assert checks["all_evidence_packets_closed"]["status"] == "BLOCKED"
    assert checks["study_implementation_gap_audit"]["status"] == "PASS"
    assert checks["all_study_implementations_ready"]["status"] == "BLOCKED"
    assert checks["MV4_production_artifact"]["status"] == "BLOCKED"
    assert checks["thesis_pdf_html"]["status"] == "BLOCKED"

    generate_thesis_draft(run)
    generate_publication_index(run)
    generate_wiki_export(run)
    audit_after_wiki = generate_release_audit(run, include_claim_ledger=True)
    checks_after_wiki = {check["name"]: check for check in audit_after_wiki["checks"]}
    assert checks_after_wiki["wiki_claim_evidence_matrix"]["status"] == "PASS"
    assert checks_after_wiki["wiki_claim_evidence_matrix"]["listed_in_manifest"] is True
    assert checks_after_wiki["wiki_claim_evidence_matrix"]["size_bytes"] > 0

    assert (run / "QA_RELEASE_AUDIT.json").is_file()
    md = (run / "QA_RELEASE_AUDIT.md").read_text(encoding="utf-8")
    assert "release QA audit" in md
    assert "MV4_production_artifact" in md
    assert "Release ready:** `False`" in md
