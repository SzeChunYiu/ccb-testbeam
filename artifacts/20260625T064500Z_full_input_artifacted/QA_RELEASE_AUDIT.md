# MC Validation release QA audit

- **Run ID:** `20260625T064500Z_full_input_artifacted`
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
| open_question_registry | PASS |  |
| open_question_closure_plan | PASS |  |
| open_question_evidence_packets | PASS |  |
| study_implementation_gap_audit | PASS |  |
| claim_ledger | PASS |  |
| MV1_production_artifact | PASS |  |
| MV2_production_artifact | PASS |  |
| MV3_production_artifact | PASS |  |
| MV4_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| MV5_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| MV6_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| MV7_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| MV8_production_artifact | BLOCKED | requires calibrated digitized MC/systematics production artifacts |
| all_questions_closed | BLOCKED | expected all_questions_closed=True, observed False |
| all_question_steps_closed | BLOCKED | expected all_steps_closed=True, observed False |
| all_evidence_packets_closed | BLOCKED | expected all_packets_closed=True, observed False |
| all_study_implementations_ready | BLOCKED | expected all_study_implementations_ready=True, observed False |
| systematic_arrays | BLOCKED | required systematic/bootstrap arrays are not complete |
| full_figure_catalog | BLOCKED | required 300-entry figure catalog/contact sheets are not complete |
| clean_kernel_notebooks | BLOCKED | full-data notebooks have not been executed via LUNARC sbatch |
| thesis_pdf_html | BLOCKED | thesis/static site PDF/HTML package is not built |
| release_bundle | BLOCKED | final release bundle/signoff is not complete |

## Guardrail

A `BLOCKED` release audit is expected until MV4-MV8, systematic arrays, the full figure catalog, clean-kernel notebooks, thesis/static site, and release bundle are completed and validated.
