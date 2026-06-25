"""Release orchestrator publication integration tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.execution.pipeline import PipelineOrchestrator
from ccb_mc_validation.reporting.artifact_reports import generate_artifact_reports
from ccb_mc_validation.reporting.claim_ledger import generate_claim_ledger
from ccb_mc_validation.reporting.figure_manifest import generate_summary_figure_manifest
from ccb_mc_validation.reporting.notebook_summary import generate_notebook_exports
from ccb_mc_validation.reporting.release_audit import generate_release_audit
from ccb_mc_validation.reporting.run_summary import generate_run_summary
from ccb_mc_validation.reporting.thesis_draft import generate_thesis_draft
from ccb_mc_validation.reporting.visual_review import generate_summary_visual_review


def _seed_run(run: Path) -> None:
    run.mkdir(parents=True)
    validation = {
        "run_id": run.name,
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


def test_release_orchestrator_generates_reference_before_publication_index(tmp_path: Path) -> None:
    repo = Path.cwd()
    run_id = "run-release-order"
    run = repo / "reports" / "mc_validation" / "runs" / run_id
    if run.exists():
        import shutil
        shutil.rmtree(run)
    _seed_run(run)
    orch = PipelineOrchestrator(repo / "configs" / "mc_validation" / "execution.yaml", repo_root=repo, run_id=run_id)

    result = orch.release()

    assert result["status"] == "BLOCKED"
    publication = json.loads((run / "publication" / "PUBLICATION_MANIFEST.json").read_text(encoding="utf-8"))
    assert publication["links"]["reference_registry"]["exists"] is True
    assert (run / "reports" / "mc_validation" / "references" / "REFERENCE_REGISTRY.md").is_file()
    import shutil
    shutil.rmtree(run)
