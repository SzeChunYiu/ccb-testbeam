# Discussion, limitations, and blockers

## Interpretation

The frozen artifacts support only a partial MC-validation narrative: MV1-MV3/MV9 artifact summaries are internally consistent, while release claims remain blocked.

## Blocked release claims

- `CLAIM-MV4-RELEASE`: Blocked pending calibrated digitized MC/systematic production artifacts.
- `CLAIM-MV5-RELEASE`: Blocked pending calibrated digitized MC/systematic production artifacts.
- `CLAIM-MV6-RELEASE`: Blocked pending calibrated digitized MC/systematic production artifacts.
- `CLAIM-MV7-RELEASE`: Blocked pending calibrated digitized MC/systematic production artifacts.
- `CLAIM-MV8-RELEASE`: Blocked pending calibrated digitized MC/systematic production artifacts.
- `CLAIM-FINAL-RELEASE`: Release requires every QA audit gate to pass; current blocked gates must remain visible.

## Release-audit blockers

- `wiki_claim_evidence_matrix`: missing wiki manifest
- `wiki_claim_dependency_tree`: missing wiki manifest
- `wiki_study_coverage_gaps`: missing wiki manifest
- `MV4_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `MV5_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `MV6_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `MV7_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `MV8_production_artifact`: requires calibrated digitized MC/systematics production artifacts
- `all_questions_closed`: expected all_questions_closed=True, observed False
- `all_question_steps_closed`: expected all_steps_closed=True, observed False
- `all_evidence_packets_closed`: expected all_packets_closed=True, observed False
- `all_study_implementations_ready`: expected all_study_implementations_ready=True, observed False
- `systematic_arrays`: required systematic/bootstrap arrays are not complete
- `full_figure_catalog`: required 300-entry figure catalog/contact sheets are not complete
- `clean_kernel_notebooks`: full-data notebooks have not been executed via LUNARC sbatch
- `thesis_pdf_html`: thesis/static site PDF/HTML package is not built
- `release_bundle`: final release bundle/signoff is not complete
