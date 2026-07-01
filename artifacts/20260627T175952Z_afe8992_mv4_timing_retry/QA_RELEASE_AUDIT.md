# MC Validation release QA audit

- **Run ID:** `20260627T175952Z_afe8992_mv4_timing_retry`
- **Status:** **BLOCKED**
- **Release ready:** `False`

| Check | Status | Reason |
|---|---:|---|
| artifact_validation | PASS |  |
| run_summary_html | PASS |  |
| run_summary_metrics | PASS |  |
| artifact_notebook_manifest | PASS |  |
| artifact_report_manifest | PASS |  |
| summary_figure_manifest | PASS |  |
| summary_visual_review | PASS |  |
| open_question_registry | BLOCKED | missing artifact |
| open_question_closure_plan | BLOCKED | missing artifact |
| open_question_evidence_packets | BLOCKED | missing artifact |
| study_implementation_gap_audit | BLOCKED | missing artifact |
| claim_ledger | PASS |  |
| wiki_claim_evidence_matrix | BLOCKED | missing wiki manifest |
| wiki_claim_dependency_tree | BLOCKED | missing wiki manifest |
| wiki_study_coverage_gaps | BLOCKED | missing wiki manifest |
| MV1_production_artifact | PASS |  |
| MV2_production_artifact | PASS |  |
| MV3_production_artifact | PASS |  |
| MV4_production_artifact | PASS |  |
| MV4_timing_uncertainty_artifact | BLOCKED | expected status=PASS, observed PRODUCTION |
| MV5_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| MV6_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| MV7_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| MV8_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| all_questions_closed | BLOCKED | missing artifact |
| all_question_steps_closed | BLOCKED | missing artifact |
| all_evidence_packets_closed | BLOCKED | missing artifact |
| all_study_implementations_ready | BLOCKED | missing artifact |
| systematic_arrays | BLOCKED | required systematic/bootstrap arrays are not complete |
| full_figure_catalog | BLOCKED | required 300-entry figure catalog/contact sheets are not complete |
| clean_kernel_notebooks | BLOCKED | full-data notebooks have not been executed via LUNARC sbatch |
| thesis_pdf_html | BLOCKED | thesis/static site PDF/HTML package is not built |
| release_bundle | BLOCKED | final release bundle/signoff is not complete |

## Guardrail

A `BLOCKED` release audit is expected until MV4-MV8, systematic arrays, the full figure catalog, clean-kernel notebooks, thesis/static site, and release bundle are completed and validated.
